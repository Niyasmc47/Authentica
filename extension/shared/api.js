/**
 * Authentica Extension — Backend API Integration Client
 */

import { DEFAULT_API_URL, DEFAULT_WEB_APP_URL, STORAGE_KEYS } from './constants.js';

/**
 * Retrieves configured Backend API URL with default fallback.
 */
export async function getApiUrl() {
  try {
    const data = await chrome.storage.local.get(STORAGE_KEYS.API_URL);
    return data[STORAGE_KEYS.API_URL] || DEFAULT_API_URL;
  } catch {
    return DEFAULT_API_URL;
  }
}

/**
 * Retrieves configured Web Application URL with default fallback.
 */
export async function getWebAppUrl() {
  try {
    const data = await chrome.storage.local.get(STORAGE_KEYS.WEB_APP_URL);
    return data[STORAGE_KEYS.WEB_APP_URL] || DEFAULT_WEB_APP_URL;
  } catch {
    return DEFAULT_WEB_APP_URL;
  }
}

/**
 * Performs a fast health verification check against the backend.
 */
export async function checkBackendHealth(apiUrl) {
  const target = apiUrl || (await getApiUrl());
  try {
    const res = await fetch(`${target}/api/health`, {
      method: 'GET',
      headers: { 'Accept': 'application/json' },
      signal: AbortSignal.timeout(4000),
    });
    if (!res.ok) {
      return { ok: false, error: `Backend responded with HTTP ${res.status}` };
    }
    const data = await res.json();
    return { ok: true, data };
  } catch (err) {
    return { ok: false, error: err.message || 'Cannot reach Authentica backend service' };
  }
}

/**
 * Uploads a captured media clip (WebM Blob) to the existing Authentica backend pipeline.
 * Reuses POST /api/analyses (Stage 1 -> Stage 2 -> Stage 3).
 *
 * @param {Blob} mediaBlob - Recorded WebM media clip
 * @param {string} [filename] - Upload filename
 * @param {object} [metadata] - Optional tab metadata
 */
export async function uploadClipForAnalysis(mediaBlob, filename, metadata = {}) {
  const apiUrl = await getApiUrl();
  const webAppUrl = await getWebAppUrl();

  if (!mediaBlob || mediaBlob.size === 0) {
    throw new Error('Recorded media clip is empty (0 bytes). Scan aborted.');
  }

  const uploadName = filename || `tab_capture_${Date.now()}.webm`;
  const formData = new FormData();
  formData.append('file', mediaBlob, uploadName);

  let response;
  try {
    response = await fetch(`${apiUrl}/api/analyses`, {
      method: 'POST',
      body: formData,
      headers: {
        'Accept': 'application/json',
      },
    });
  } catch (err) {
    throw new Error(`Analysis server unavailable at ${apiUrl}. Please verify the backend is running.`);
  }

  if (!response.ok) {
    let detail = `Server returned HTTP ${response.status}`;
    try {
      const errJson = await response.json();
      if (errJson.detail) {
        detail = typeof errJson.detail === 'string' ? errJson.detail : JSON.stringify(errJson.detail);
      }
    } catch {
      // ignore json parse error
    }

    if (response.status === 413) {
      throw new Error(`Captured clip exceeded maximum upload size limit: ${detail}`);
    } else if (response.status === 422 || response.status === 400) {
      throw new Error(`Media validation failed: ${detail}`);
    } else {
      throw new Error(`Analysis failed (${response.status}): ${detail}`);
    }
  }

  const data = await response.json();

  // Extract compact warning summary without altering backend verdicts
  const summary = {
    id: data.id,
    status: data.status,
    action: data.assessment?.action || 'VERIFY',
    mediaVerdict: data.assessment?.media || 'UNCERTAIN',
    fraudLevel: data.assessment?.fraud || data.fraud?.level || 'LOW',
    visualManipulationProb: data.visual?.manipulation_probability || 0,
    visualIsDeepfake: Boolean(data.visual?.is_deepfake),
    audioSpoofProb: data.audio?.spoof_probability || 0,
    audioIsSpoof: Boolean(data.audio?.is_spoof),
    fraudRiskScore: data.fraud?.risk_score || 0,
    requestedAction: data.fraud?.requested_actions?.[0]?.action || null,
    explanations: Array.isArray(data.explanation) ? data.explanation.slice(0, 3) : [],
    fullReportUrl: `${webAppUrl}/results/${data.id}`,
    timestamp: Date.now(),
    capturedTabTitle: metadata.tabTitle || 'Current Tab',
    capturedTabUrl: metadata.tabUrl || '',
  };

  return { raw: data, summary };
}
