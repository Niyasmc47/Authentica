/**
 * Authentica Extension — MV3 Background Service Worker
 *
 * Coordinates:
 * 1. Live continuous tab monitoring mode with silent safe state and instant risk alerting
 * 2. Manual 8-second quick scans
 * 3. Offscreen document lifecycle & audio loopback preservation
 * 4. Automatic reconnection on tab reload
 * 5. Badge status indicators and notification dispatch
 */

import {
  MESSAGE_TYPES,
  MONITORING_STATES,
  OFFSCREEN_DOCUMENT_PATH,
  POPUP_STATES,
  STORAGE_KEYS,
} from '../shared/constants.js';

// Global Extension State
let state = {
  // Monitoring mode
  monitoringActive: false,
  monitoredTabId: null,
  monitoredTabTitle: '',
  monitoredTabUrl: '',
  monitoringStatus: MONITORING_STATES.OFF,
  activeThreat: null,
  lastCheckTime: null,
  cyclesCompleted: 0,

  // Quick scan mode
  quickScan: {
    state: POPUP_STATES.IDLE,
    secondsRemaining: 8,
    tabId: null,
    tabTitle: '',
    tabUrl: '',
    message: '',
    errorDetail: '',
    summary: null,
  },
};

// Initialize extension lifecycle
chrome.runtime.onInstalled.addListener(() => {
  console.info('[Authentica Service Worker] Installed.');
  saveStateToStorage();
});

// Watch for tab reload / navigation
chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  if (state.monitoringActive && state.monitoredTabId === tabId) {
    if (changeInfo.status === 'complete') {
      console.info(`[Service Worker] Monitored tab ${tabId} finished reloading. Reconnecting protection...`);
      state.monitoredTabTitle = tab.title || state.monitoredTabTitle;
      state.monitoredTabUrl = tab.url || state.monitoredTabUrl;

      // Small delay to ensure tab media renderer is ready
      setTimeout(async () => {
        if (state.monitoringActive && state.monitoredTabId === tabId) {
          try {
            await startMonitoringOnTab(tabId, state.monitoredTabTitle, state.monitoredTabUrl);
          } catch (err) {
            console.warn('[Service Worker] Auto-resume after reload failed:', err);
          }
        }
      }, 1000);
    }
  }
});

// Watch for tab close
chrome.tabs.onRemoved.addListener((tabId) => {
  if (state.monitoredTabId === tabId) {
    console.info(`[Service Worker] Monitored tab ${tabId} closed. Stopping protection.`);
    stopMonitoring();
  }
});

// Inter-context message dispatcher
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || !message.type) return;

  switch (message.type) {
    case MESSAGE_TYPES.GET_STATE:
      sendResponse(state);
      return false;

    // --- LIVE TAB MONITORING ---
    case MESSAGE_TYPES.START_MONITORING:
      startMonitoringOnTab(message.payload.tabId, message.payload.tabTitle, message.payload.tabUrl)
        .then(() => sendResponse({ ok: true }))
        .catch((err) => sendResponse({ ok: false, error: err.message }));
      return true;

    case MESSAGE_TYPES.STOP_MONITORING:
      stopMonitoring();
      sendResponse({ ok: true });
      return false;

    case MESSAGE_TYPES.DISMISS_THREAT:
      state.activeThreat = null;
      state.monitoringStatus = MONITORING_STATES.MONITORING_SAFE;
      setBadgeSafe();
      saveStateToStorage();
      broadcastState();
      sendResponse({ ok: true });
      return false;

    case 'MONITORING_CHUNK_RESULT':
      handleMonitoringChunkResult(message.payload);
      sendResponse({ ok: true });
      return false;

    case 'TAB_TRACK_ENDED':
      console.info('[Service Worker] Tab media track ended.');
      return false;

    // --- MANUAL QUICK SCAN ---
    case MESSAGE_TYPES.START_SCAN:
      handleStartQuickScan(message.payload)
        .then(() => sendResponse({ ok: true }))
        .catch((err) => {
          setQuickScanError(err.message || 'Failed to start tab scan.');
          sendResponse({ ok: false, error: err.message });
        });
      return true;

    case MESSAGE_TYPES.CANCEL_SCAN:
      handleCancelQuickScan();
      sendResponse({ ok: true });
      return false;

    case MESSAGE_TYPES.RESET_STATE:
      resetQuickScanState();
      sendResponse(state);
      return false;

    case MESSAGE_TYPES.STATUS_UPDATE:
      state.quickScan.state = message.payload.state;
      if (message.payload.message) state.quickScan.message = message.payload.message;
      if (message.payload.secondsRemaining !== undefined) state.quickScan.secondsRemaining = message.payload.secondsRemaining;
      saveStateToStorage();
      broadcastState();
      sendResponse({ acknowledged: true });
      return false;

    case MESSAGE_TYPES.RECORDING_TICK:
      state.quickScan.secondsRemaining = message.payload.secondsRemaining;
      broadcastState();
      sendResponse({ acknowledged: true });
      return false;

    case MESSAGE_TYPES.SCAN_COMPLETE:
      state.quickScan.state = POPUP_STATES.COMPLETED;
      state.quickScan.summary = message.payload.summary;
      state.quickScan.errorDetail = '';
      state.quickScan.message = 'Analysis complete.';
      saveStateToStorage();
      broadcastState();
      sendResponse({ acknowledged: true });
      return false;

    case MESSAGE_TYPES.SCAN_ERROR:
      setQuickScanError(message.payload.error);
      sendResponse({ acknowledged: true });
      return false;

    default:
      return false;
  }
});

/**
 * Initiates continuous monitoring on the specified tab.
 */
async function startMonitoringOnTab(tabId, tabTitle, tabUrl) {
  if (!tabId) throw new Error('No active browser tab found.');
  if (isRestrictedUrl(tabUrl)) {
    throw new Error('Internal browser pages (chrome://) cannot be captured.');
  }

  state.monitoringActive = true;
  state.monitoredTabId = tabId;
  state.monitoredTabTitle = tabTitle || 'Current Tab';
  state.monitoredTabUrl = tabUrl || '';
  state.monitoringStatus = MONITORING_STATES.MONITORING_SAFE;
  state.activeThreat = null;
  state.cyclesCompleted = 0;

  setBadgeSafe();
  saveStateToStorage();
  broadcastState();

  const streamId = await acquireStreamId(tabId);
  await ensureOffscreenDocument();

  chrome.runtime.sendMessage({
    type: MESSAGE_TYPES.START_MONITORING,
    payload: {
      streamId,
      tabId,
      tabTitle: state.monitoredTabTitle,
      tabUrl: state.monitoredTabUrl,
    },
  });
}

/**
 * Evaluates completed monitoring chunk and raises threat alert ONLY if risk detected.
 */
function handleMonitoringChunkResult({ summary, raw }) {
  if (!state.monitoringActive || !summary) return;

  const isRisk = evaluateRisk(summary, raw);

  if (isRisk) {
    // THREAT DETECTED: Immediately alert the user!
    console.warn('[Service Worker] THREAT DETECTED on monitored tab:', summary);
    state.monitoringStatus = MONITORING_STATES.THREAT_ALERT;
    state.activeThreat = summary;

    setBadgeRisk();

    // Trigger desktop notification
    if (chrome.notifications && chrome.notifications.create) {
      chrome.notifications.create({
        type: 'basic',
        iconUrl: 'icons/icon128.png',
        title: '⚠️ Authentica Deepfake Alert',
        message: `High risk detected on "${state.monitoredTabTitle}": ${summary.action || 'VERIFY'}`,
        priority: 2,
      });
    }
  } else {
    // SAFE: Stay quiet! Increment cycle count and keep silent protection running
    state.monitoringStatus = MONITORING_STATES.MONITORING_SAFE;
    state.cyclesCompleted += 1;
    state.lastCheckTime = Date.now();
    setBadgeSafe();
  }

  saveStateToStorage();
  broadcastState();
}

/**
 * Determines whether a clip exhibits forensic deepfake or social engineering fraud risk.
 */
function evaluateRisk(summary, raw) {
  // 1. Backend action directive
  if (summary.action === 'STOP_AND_VERIFY' || summary.action === 'CAUTION') return true;

  // 2. Visual face manipulation
  if (summary.mediaVerdict === 'MANIPULATED' || summary.mediaVerdict === 'LIKELY_MANIPULATED') return true;
  if (summary.visualIsDeepfake || (summary.visualManipulationProb && summary.visualManipulationProb >= 0.50)) return true;

  // 3. Audio voice anti-spoofing
  if (summary.audioIsSpoof || (summary.audioSpoofProb && summary.audioSpoofProb >= 0.50)) return true;

  // 4. Fraud intent & social engineering
  if (summary.fraudLevel === 'HIGH' || summary.fraudLevel === 'CRITICAL') return true;
  if (summary.requestedAction) return true;
  if (summary.fraudRiskScore && summary.fraudRiskScore >= 0.40) return true;

  return false;
}

/**
 * Cleanly stops monitoring and resets badge.
 */
function stopMonitoring() {
  state.monitoringActive = false;
  state.monitoredTabId = null;
  state.monitoringStatus = MONITORING_STATES.OFF;
  state.activeThreat = null;

  clearBadge();
  saveStateToStorage();
  broadcastState();

  try {
    chrome.runtime.sendMessage({ type: MESSAGE_TYPES.STOP_MONITORING });
  } catch {}

  closeOffscreenDocumentQuietly();
}

/**
 * Initiates single manual 8-second quick scan.
 */
async function handleStartQuickScan({ tabId, tabTitle, tabUrl }) {
  if (!tabId) throw new Error('No active browser tab found.');
  if (isRestrictedUrl(tabUrl)) {
    throw new Error('Internal browser pages (chrome://) cannot be captured.');
  }

  state.quickScan = {
    state: POPUP_STATES.CAPTURING,
    secondsRemaining: 8,
    tabId,
    tabTitle: tabTitle || 'Current Tab',
    tabUrl: tabUrl || '',
    message: 'Capturing current tab...',
    errorDetail: '',
    summary: null,
  };

  saveStateToStorage();
  broadcastState();

  const streamId = await acquireStreamId(tabId);
  await ensureOffscreenDocument();

  chrome.runtime.sendMessage({
    type: MESSAGE_TYPES.START_RECORDING,
    payload: {
      streamId,
      tabId,
      tabTitle: state.quickScan.tabTitle,
      tabUrl: state.quickScan.tabUrl,
    },
  });
}

function handleCancelQuickScan() {
  try {
    chrome.runtime.sendMessage({ type: MESSAGE_TYPES.CANCEL_SCAN });
  } catch {}
  resetQuickScanState();
}

function resetQuickScanState() {
  state.quickScan = {
    state: POPUP_STATES.IDLE,
    secondsRemaining: 8,
    tabId: null,
    tabTitle: '',
    tabUrl: '',
    message: '',
    errorDetail: '',
    summary: null,
  };
  saveStateToStorage();
  broadcastState();
}

function setQuickScanError(msg) {
  state.quickScan.state = POPUP_STATES.ERROR;
  state.quickScan.errorDetail = msg || 'Capture failed.';
  state.quickScan.message = 'Capture failed.';
  saveStateToStorage();
  broadcastState();
}

// Helpers
async function acquireStreamId(tabId) {
  try {
    const streamId = await chrome.tabCapture.getMediaStreamId({ targetTabId: tabId });
    if (!streamId) throw new Error('Chrome did not return a valid stream ID.');
    return streamId;
  } catch (err) {
    throw new Error('Failed to acquire tab capture permission.');
  }
}

async function hasOffscreenDocument() {
  if (chrome.offscreen && typeof chrome.offscreen.hasDocument === 'function') {
    return await chrome.offscreen.hasDocument();
  }
  if (chrome.runtime && typeof chrome.runtime.getContexts === 'function') {
    try {
      const contexts = await chrome.runtime.getContexts({ contextTypes: ['OFFSCREEN_DOCUMENT'] });
      return Boolean(contexts && contexts.length > 0);
    } catch {
      return false;
    }
  }
  return false;
}

async function ensureOffscreenDocument() {
  const exists = await hasOffscreenDocument();
  if (exists) return;

  try {
    await chrome.offscreen.createDocument({
      url: OFFSCREEN_DOCUMENT_PATH,
      reasons: ['USER_MEDIA'],
      justification: 'Authentica tab capture for synthetic deepfake analysis',
    });
  } catch (err) {
    if (!err.message?.includes('Only a single offscreen document may be created')) {
      throw err;
    }
  }
}

async function closeOffscreenDocumentQuietly() {
  try {
    const exists = await hasOffscreenDocument();
    if (exists && chrome.offscreen?.closeDocument) {
      await chrome.offscreen.closeDocument();
    }
  } catch {}
}

function isRestrictedUrl(url) {
  if (!url) return false;
  const restricted = ['chrome://', 'chrome-extension://', 'devtools://', 'edge://', 'about:', 'view-source:'];
  return restricted.some((prefix) => url.startsWith(prefix));
}

// Badge Indicators
function setBadgeSafe() {
  try {
    chrome.action.setBadgeText({ text: 'ON' });
    chrome.action.setBadgeBackgroundColor({ color: '#10b981' }); // Emerald Green
  } catch {}
}

function setBadgeRisk() {
  try {
    chrome.action.setBadgeText({ text: 'RISK' });
    chrome.action.setBadgeBackgroundColor({ color: '#ef4444' }); // Red
  } catch {}
}

function clearBadge() {
  try {
    chrome.action.setBadgeText({ text: '' });
  } catch {}
}

function saveStateToStorage() {
  try {
    chrome.storage.local.set({ [STORAGE_KEYS.CURRENT_SCAN]: state });
  } catch {}
}

function broadcastState() {
  try {
    chrome.runtime.sendMessage({
      type: MESSAGE_TYPES.STATUS_UPDATE,
      payload: state,
    }).catch(() => {});
  } catch {}
}
