/**
 * Authentica Extension — Streamlined Popup Controller
 */

import {
  DEFAULT_API_URL,
  DEFAULT_WEB_APP_URL,
  MESSAGE_TYPES,
  MONITORING_STATES,
  POPUP_STATES,
  STORAGE_KEYS,
} from '../shared/constants.js';

import { checkBackendHealth, getApiUrl, getWebAppUrl } from '../shared/api.js';

// DOM Elements
const elements = {
  // Brand & Settings
  btnSettingsToggle: document.getElementById('btnSettingsToggle'),
  settingsDrawer: document.getElementById('settingsDrawer'),
  btnCloseSettings: document.getElementById('btnCloseSettings'),
  inputApiUrl: document.getElementById('inputApiUrl'),
  inputWebAppUrl: document.getElementById('inputWebAppUrl'),
  btnSaveSettings: document.getElementById('btnSaveSettings'),
  settingsFeedback: document.getElementById('settingsFeedback'),

  // Context
  tabHost: document.getElementById('tabHost'),

  // Views
  viewIdle: document.getElementById('viewIdle'),
  viewMonitoringSafe: document.getElementById('viewMonitoringSafe'),
  viewThreatAlert: document.getElementById('viewThreatAlert'),
  viewScanning: document.getElementById('viewScanning'),
  viewError: document.getElementById('viewError'),

  // Idle controls
  btnEnableProtection: document.getElementById('btnEnableProtection'),
  btnQuickScan: document.getElementById('btnQuickScan'),

  // Monitoring Safe controls
  statCycles: document.getElementById('statCycles'),
  btnStopProtection: document.getElementById('btnStopProtection'),

  // Threat Alert controls
  threatActionBanner: document.getElementById('threatActionBanner'),
  rowAudioRisk: document.getElementById('rowAudioRisk'),
  textAudioRisk: document.getElementById('textAudioRisk'),
  rowVideoRisk: document.getElementById('rowVideoRisk'),
  textVideoRisk: document.getElementById('textVideoRisk'),
  rowFraudRisk: document.getElementById('rowFraudRisk'),
  textFraudRisk: document.getElementById('textFraudRisk'),
  btnOpenThreatReport: document.getElementById('btnOpenThreatReport'),
  btnDismissThreat: document.getElementById('btnDismissThreat'),

  // Quick Scan controls
  countdownVal: document.getElementById('countdownVal'),
  scanningTitle: document.getElementById('scanningTitle'),
  scanningDesc: document.getElementById('scanningDesc'),
  btnCancelScan: document.getElementById('btnCancelScan'),

  // Error controls
  errorMsgText: document.getElementById('errorMsgText'),
  btnResetView: document.getElementById('btnResetView'),

  // Footer
  backendStatusLabel: document.getElementById('backendStatusLabel'),
  btnOpenWeb: document.getElementById('btnOpenWeb'),
};

let currentTab = null;
let activeThreatSummary = null;

// Initialization
document.addEventListener('DOMContentLoaded', async () => {
  setupEventListeners();
  await detectActiveTab();
  await loadSettings();
  await checkHealth();
  await syncStateWithServiceWorker();
});

// Broadcast listener from background service worker
chrome.runtime.onMessage.addListener((message) => {
  if (!message) return;

  if (message.type === MESSAGE_TYPES.STATUS_UPDATE && message.payload) {
    applyGlobalState(message.payload);
  } else if (message.type === MESSAGE_TYPES.RECORDING_TICK && message.payload) {
    if (elements.countdownVal) {
      elements.countdownVal.textContent = Math.max(0, message.payload.secondsRemaining);
    }
  }
});

function setupEventListeners() {
  // Protection toggles
  elements.btnEnableProtection.addEventListener('click', handleEnableProtectionClick);
  elements.btnStopProtection.addEventListener('click', handleStopProtectionClick);

  // Quick scan
  elements.btnQuickScan.addEventListener('click', handleStartQuickScanClick);
  elements.btnCancelScan.addEventListener('click', handleCancelQuickScanClick);

  // Threat actions
  elements.btnOpenThreatReport.addEventListener('click', handleOpenThreatReportClick);
  elements.btnDismissThreat.addEventListener('click', handleDismissThreatClick);

  // Error
  elements.btnResetView.addEventListener('click', () => showView(elements.viewIdle));

  // Settings
  elements.btnSettingsToggle.addEventListener('click', () => {
    elements.settingsDrawer.classList.toggle('hidden');
  });
  elements.btnCloseSettings.addEventListener('click', () => {
    elements.settingsDrawer.classList.add('hidden');
  });
  elements.btnSaveSettings.addEventListener('click', handleSaveSettingsClick);

  // Footer Web App Link
  elements.btnOpenWeb.addEventListener('click', async () => {
    const webAppUrl = await getWebAppUrl();
    chrome.tabs.create({ url: webAppUrl });
  });
}

/**
 * Detects current active tab in Chrome.
 */
async function detectActiveTab() {
  try {
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tabs || tabs.length === 0) {
      elements.tabHost.textContent = 'No tab focused';
      disableActionButtons('No tab focused');
      return;
    }

    currentTab = tabs[0];
    if (currentTab.url) {
      try {
        const u = new URL(currentTab.url);
        elements.tabHost.textContent = u.hostname || currentTab.title || 'Active Tab';
      } catch {
        elements.tabHost.textContent = currentTab.title || 'Active Tab';
      }

      if (isRestrictedUrl(currentTab.url)) {
        elements.tabHost.textContent = 'Browser Internal Page (Restricted)';
        disableActionButtons('Capture not available on internal pages');
      }
    }
  } catch (err) {
    console.warn('[Popup] Error querying tabs:', err);
  }
}

function isRestrictedUrl(url) {
  if (!url) return true;
  const restricted = ['chrome://', 'chrome-extension://', 'devtools://', 'edge://', 'about:', 'view-source:'];
  return restricted.some((prefix) => url.startsWith(prefix));
}

function disableActionButtons(reason) {
  elements.btnEnableProtection.disabled = true;
  elements.btnQuickScan.disabled = true;
  elements.btnEnableProtection.title = reason;
  elements.btnQuickScan.title = reason;
}

/**
 * Syncs UI with background service worker state.
 */
async function syncStateWithServiceWorker() {
  try {
    chrome.runtime.sendMessage({ type: MESSAGE_TYPES.GET_STATE }, (response) => {
      if (chrome.runtime.lastError || !response) {
        showView(elements.viewIdle);
        return;
      }
      applyGlobalState(response);
    });
  } catch {
    showView(elements.viewIdle);
  }
}

/**
 * Applies global service worker state to the popup views.
 */
function applyGlobalState(state) {
  if (!state) return;

  // 1. If a threat is actively flagged:
  if (state.monitoringStatus === MONITORING_STATES.THREAT_ALERT || state.activeThreat) {
    renderThreatAlert(state.activeThreat);
    return;
  }

  // 2. If quick scan is actively running:
  if (state.quickScan && state.quickScan.state === POPUP_STATES.CAPTURING) {
    elements.scanningTitle.textContent = 'Capturing Tab Media';
    elements.scanningDesc.textContent = 'Audio playback remains audible while capturing...';
    if (elements.countdownVal) {
      elements.countdownVal.textContent = state.quickScan.secondsRemaining || 8;
    }
    showView(elements.viewScanning);
    return;
  }

  if (state.quickScan && (state.quickScan.state === POPUP_STATES.UPLOADING || state.quickScan.state === POPUP_STATES.ANALYZING)) {
    elements.scanningTitle.textContent = 'Analyzing Forensic Models';
    elements.scanningDesc.textContent = 'Running EfficientNet, AASIST & Fraud Engine...';
    showView(elements.viewScanning);
    return;
  }

  if (state.quickScan && state.quickScan.state === POPUP_STATES.COMPLETED && state.quickScan.summary) {
    renderThreatAlert(state.quickScan.summary);
    return;
  }

  if (state.quickScan && state.quickScan.state === POPUP_STATES.ERROR) {
    renderError(state.quickScan.errorDetail);
    return;
  }

  // 3. If continuous monitoring is ON and safe:
  if (state.monitoringActive && state.monitoringStatus === MONITORING_STATES.MONITORING_SAFE) {
    elements.statCycles.textContent = state.cyclesCompleted || 0;
    showView(elements.viewMonitoringSafe);
    return;
  }

  // 4. Default: Idle
  showView(elements.viewIdle);
}

/**
 * Displays the appropriate single view card.
 */
function showView(targetView) {
  [
    elements.viewIdle,
    elements.viewMonitoringSafe,
    elements.viewThreatAlert,
    elements.viewScanning,
    elements.viewError,
  ].forEach((v) => {
    if (v) v.classList.add('hidden');
  });

  if (targetView) {
    targetView.classList.remove('hidden');
  }
}

/**
 * Handles "Turn On Protection" click.
 */
function handleEnableProtectionClick() {
  if (!currentTab) return;

  chrome.runtime.sendMessage({
    type: MESSAGE_TYPES.START_MONITORING,
    payload: {
      tabId: currentTab.id,
      tabTitle: currentTab.title,
      tabUrl: currentTab.url,
    },
  }, (response) => {
    if (chrome.runtime.lastError || (response && !response.ok)) {
      renderError(response?.error || 'Could not start live protection on this tab.');
    } else {
      showView(elements.viewMonitoringSafe);
    }
  });
}

/**
 * Handles "Stop Protection" click.
 */
function handleStopProtectionClick() {
  chrome.runtime.sendMessage({ type: MESSAGE_TYPES.STOP_MONITORING });
  showView(elements.viewIdle);
}

/**
 * Handles single quick scan.
 */
function handleStartQuickScanClick() {
  if (!currentTab) return;

  chrome.runtime.sendMessage({
    type: MESSAGE_TYPES.START_SCAN,
    payload: {
      tabId: currentTab.id,
      tabTitle: currentTab.title,
      tabUrl: currentTab.url,
    },
  }, (response) => {
    if (chrome.runtime.lastError || (response && !response.ok)) {
      renderError(response?.error || 'Could not capture current tab.');
    } else {
      showView(elements.viewScanning);
    }
  });
}

function handleCancelQuickScanClick() {
  chrome.runtime.sendMessage({ type: MESSAGE_TYPES.CANCEL_SCAN });
  showView(elements.viewIdle);
}

/**
 * Renders prominent Threat Detected warning card with specific risk breakdown.
 */
function renderThreatAlert(summary) {
  if (!summary) return;
  activeThreatSummary = summary;

  // Action Banner
  elements.threatActionBanner.textContent = summary.action || 'STOP AND VERIFY';

  // Audio risk row
  const hasAudioRisk = summary.audioIsSpoof || (summary.audioSpoofProb && summary.audioSpoofProb >= 0.50);
  if (hasAudioRisk) {
    elements.rowAudioRisk.classList.remove('hidden');
    elements.textAudioRisk.textContent = `Audio synthetic voice spoof flagged (${Math.round((summary.audioSpoofProb || 0.85) * 100)}%)`;
  } else {
    elements.rowAudioRisk.classList.add('hidden');
  }

  // Video risk row
  const hasVideoRisk = summary.visualIsDeepfake || (summary.visualManipulationProb && summary.visualManipulationProb >= 0.50) || summary.mediaVerdict === 'MANIPULATED';
  if (hasVideoRisk) {
    elements.rowVideoRisk.classList.remove('hidden');
    elements.textVideoRisk.textContent = `Manipulated visual face frames flagged (${Math.round((summary.visualManipulationProb || 0.8) * 100)}%)`;
  } else {
    elements.rowVideoRisk.classList.add('hidden');
  }

  // Fraud directive row
  const hasFraudRisk = summary.requestedAction || summary.fraudLevel === 'HIGH' || summary.fraudLevel === 'CRITICAL';
  if (hasFraudRisk) {
    elements.rowFraudRisk.classList.remove('hidden');
    elements.textFraudRisk.textContent = summary.requestedAction 
      ? `High-risk directive flagged: ${summary.requestedAction}`
      : `Social engineering fraud indicators detected (${summary.fraudLevel})`;
  } else {
    elements.rowFraudRisk.classList.add('hidden');
  }

  showView(elements.viewThreatAlert);
}

/**
 * Opens full analysis report in web app.
 */
async function handleOpenThreatReportClick() {
  if (activeThreatSummary && activeThreatSummary.fullReportUrl) {
    chrome.tabs.create({ url: activeThreatSummary.fullReportUrl });
  } else if (activeThreatSummary && activeThreatSummary.id) {
    const webAppUrl = await getWebAppUrl();
    chrome.tabs.create({ url: `${webAppUrl}/results/${activeThreatSummary.id}` });
  } else {
    const webAppUrl = await getWebAppUrl();
    chrome.tabs.create({ url: webAppUrl });
  }
}

/**
 * Dismisses threat and resumes silent monitoring.
 */
function handleDismissThreatClick() {
  activeThreatSummary = null;
  chrome.runtime.sendMessage({ type: MESSAGE_TYPES.DISMISS_THREAT });
  showView(elements.viewMonitoringSafe);
}

function renderError(msg) {
  elements.errorMsgText.textContent = msg || 'Could not capture this tab.';
  showView(elements.viewError);
}

/**
 * Settings
 */
async function loadSettings() {
  const apiUrl = await getApiUrl();
  const webAppUrl = await getWebAppUrl();
  elements.inputApiUrl.value = apiUrl;
  elements.inputWebAppUrl.value = webAppUrl;
}

async function handleSaveSettingsClick() {
  const apiUrl = elements.inputApiUrl.value.trim() || DEFAULT_API_URL;
  const webAppUrl = elements.inputWebAppUrl.value.trim() || DEFAULT_WEB_APP_URL;

  await chrome.storage.local.set({
    [STORAGE_KEYS.API_URL]: apiUrl,
    [STORAGE_KEYS.WEB_APP_URL]: webAppUrl,
  });

  elements.settingsFeedback.textContent = 'Settings saved.';
  await checkHealth();
  setTimeout(() => {
    elements.settingsDrawer.classList.add('hidden');
    elements.settingsFeedback.textContent = '';
  }, 1000);
}

async function checkHealth() {
  const health = await checkBackendHealth();
  if (health.ok) {
    elements.backendStatusLabel.textContent = 'Backend Online';
    elements.backendStatusLabel.style.color = '#10b981';
  } else {
    elements.backendStatusLabel.textContent = 'Backend Offline';
    elements.backendStatusLabel.style.color = '#ef4444';
  }
}
