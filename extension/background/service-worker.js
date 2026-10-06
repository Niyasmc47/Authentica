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
    secondsRemaining: 4,
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
async function startMonitoringOnTab(tabId, tabTitle, tabUrl, preAcquiredStreamId = null) {
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

  const streamId = preAcquiredStreamId || (await acquireStreamId(tabId));
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

    // Trigger in-tab floating alert banner on the active web page
    if (state.monitoredTabId) {
      injectThreatOverlay(state.monitoredTabId, summary);
    }

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
 * Injects a floating on-screen warning toast directly into the active video page.
 */
async function injectThreatOverlay(tabId, summary) {
  if (!tabId) return;
  try {
    if (!chrome.scripting || !chrome.scripting.executeScript) return;

    await chrome.scripting.executeScript({
      target: { tabId },
      func: (threatData) => {
        const existing = document.getElementById('authentica-threat-overlay');
        if (existing) existing.remove();

        const isDeepfake = threatData.visualIsDeepfake || threatData.audioIsSpoof || threatData.mediaVerdict === 'LIKELY_MANIPULATED';
        const isSuspicious = !isDeepfake && (threatData.visualIsSuspicious || threatData.audioIsSuspicious || threatData.mediaVerdict === 'SUSPICIOUS');
        const isHarmful = threatData.fraudLevel === 'HIGH' || Boolean(threatData.requestedAction);
        const isSuspiciousHarm = !isHarmful && threatData.fraudLevel === 'MEDIUM';

        let aiBadgeText = '📷 AUTHENTIC';
        let aiBadgeColor = '#10b981';
        if (isDeepfake) {
          aiBadgeText = '⚠️ SYNTHETIC / FAKE';
          aiBadgeColor = '#ef4444';
        } else if (isSuspicious) {
          aiBadgeText = '🔍 SUSPICIOUS';
          aiBadgeColor = '#f59e0b';
        }

        let harmBadgeText = '🛡️ HARMLESS';
        let harmBadgeColor = '#10b981';
        if (isHarmful) {
          harmBadgeText = '🚨 HARMFUL SCAM';
          harmBadgeColor = '#ef4444';
        } else if (isSuspiciousHarm) {
          harmBadgeText = '⚠️ SUSPICIOUS INTENT';
          harmBadgeColor = '#f59e0b';
        }

        const overlay = document.createElement('div');
        overlay.id = 'authentica-threat-overlay';
        overlay.style.cssText = `
          position: fixed;
          top: 20px;
          right: 20px;
          z-index: 2147483647;
          background: #0f172a;
          color: #f8fafc;
          border: 1px solid rgba(239, 68, 68, 0.5);
          box-shadow: 0 10px 30px rgba(0,0,0,0.8), 0 0 20px rgba(239, 68, 68, 0.3);
          border-radius: 12px;
          padding: 16px 18px;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
          font-size: 13px;
          line-height: 1.4;
          width: 320px;
          box-sizing: border-box;
          pointer-events: auto;
          backdrop-filter: blur(8px);
        `;

        const actionText = threatData.action || 'VERIFY';
        const actionColor = actionText === 'STOP_AND_VERIFY' ? '#ef4444' : (actionText === 'CAUTION' ? '#f59e0b' : '#38bdf8');

        overlay.innerHTML = `
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 8px;">
            <div style="display:flex; align-items:center; gap:6px; font-weight:800; font-size:11px; letter-spacing:0.06em; color:#ef4444;">
              <span>🚨 AUTHENTICA SHIELD</span>
            </div>
            <button id="auth-close-overlay" style="background:transparent; border:none; color:#94a3b8; font-size:16px; cursor:pointer; padding:0 4px; line-height:1;">✕</button>
          </div>
          
          <div style="font-weight:800; font-size:15px; color:${actionColor}; margin-bottom:10px; letter-spacing:-0.01em;">
            ${actionText.replace(/_/g, ' ')}
          </div>

          <div style="background:rgba(0,0,0,0.4); border:1px solid #1e293b; border-radius:8px; padding:10px; margin-bottom:12px; display:flex; flex-direction:column; gap:6px; font-size:12px;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <span style="color:#94a3b8;">AI Deepfake Origin:</span>
              <span style="font-weight:700; color:${aiBadgeColor}; font-size:11.5px;">
                ${aiBadgeText}
              </span>
            </div>
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <span style="color:#94a3b8;">Harm / Fraud Intent:</span>
              <span style="font-weight:700; color:${harmBadgeColor}; font-size:11.5px;">
                ${harmBadgeText}
              </span>
            </div>
          </div>

          <div style="display:flex; gap:8px;">
            <a href="${threatData.fullReportUrl}" target="_blank" style="flex:1; background:#06b6d4; color:#030712; text-decoration:none; padding:8px 12px; border-radius:6px; font-weight:700; font-size:11.5px; text-align:center; display:block; transition:background 0.2s;">
              Inspect Evidence Matrix ↗
            </a>
          </div>
        `;

        document.body.appendChild(overlay);

        document.getElementById('auth-close-overlay')?.addEventListener('click', () => {
          overlay.remove();
        });

        // Auto remove after 14 seconds
        setTimeout(() => {
          if (document.body.contains(overlay)) {
            overlay.style.opacity = '0';
            overlay.style.transition = 'opacity 0.4s ease';
            setTimeout(() => overlay.remove(), 400);
          }
        }, 14000);
      },
      args: [summary],
    });
  } catch (err) {
    console.warn('[Service Worker] In-tab overlay injection error:', err);
  }
}

/**
 * Determines whether a clip exhibits forensic deepfake or social engineering fraud risk.
 */
function evaluateRisk(summary, raw) {
  if (!summary) return false;

  // 1. High risk backend action directive
  if (summary.action === 'STOP_AND_VERIFY' || summary.action === 'CAUTION') return true;

  // 2. High confidence deepfake findings
  if (summary.mediaVerdict === 'LIKELY_MANIPULATED') return true;
  if (summary.visualIsDeepfake || (summary.visualLevel === 'HIGH' && summary.visualManipulationProb >= 0.70)) return true;
  if (summary.audioIsSpoof || (summary.audioLevel === 'HIGH' && summary.audioSpoofProb >= 0.70)) return true;

  // 3. Fraud intent & social engineering
  if (summary.fraudLevel === 'HIGH' || summary.fraudLevel === 'CRITICAL') return true;
  if (summary.requestedAction) return true;

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
async function handleStartQuickScan({ tabId, tabTitle, tabUrl, streamId: preAcquiredStreamId }) {
  if (!tabId) throw new Error('No active browser tab found.');
  if (isRestrictedUrl(tabUrl)) {
    throw new Error('Internal browser pages (chrome://) cannot be captured.');
  }

  state.quickScan = {
    state: POPUP_STATES.CAPTURING,
    secondsRemaining: 4,
    tabId,
    tabTitle: tabTitle || 'Current Tab',
    tabUrl: tabUrl || '',
    message: 'Capturing current tab...',
    errorDetail: '',
    summary: null,
  };

  saveStateToStorage();
  broadcastState();

  const streamId = preAcquiredStreamId || (await acquireStreamId(tabId));
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
    secondsRemaining: 4,
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
function acquireStreamId(tabId) {
  return new Promise((resolve, reject) => {
    try {
      if (!chrome.tabCapture || typeof chrome.tabCapture.getMediaStreamId !== 'function') {
        return reject(new Error('Tab capture API is not supported or permitted in this browser profile.'));
      }

      chrome.tabCapture.getMediaStreamId({ targetTabId: tabId }, (streamId) => {
        if (chrome.runtime.lastError) {
          return reject(new Error(chrome.runtime.lastError.message || 'Failed to acquire tab capture stream ID.'));
        }
        if (!streamId) {
          return reject(new Error('Chrome did not return a valid stream ID for this tab.'));
        }
        resolve(streamId);
      });
    } catch (err) {
      reject(err);
    }
  });
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
