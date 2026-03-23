(function () {
  const STORAGE_KEYS = {
    activeSession: 'focus_active_session_v1',
    pendingCompletion: 'focus_pending_completion_v1'
  };

  function nowMs() {
    return Date.now();
  }

  function readJson(key) {
    try {
      const raw = localStorage.getItem(key);
      return raw ? JSON.parse(raw) : null;
    } catch (err) {
      return null;
    }
  }

  function writeJson(key, value) {
    localStorage.setItem(key, JSON.stringify(value));
  }

  function removeKey(key) {
    localStorage.removeItem(key);
  }

  function getSession() {
    return readJson(STORAGE_KEYS.activeSession);
  }

  function getSessionRemainingMs(session) {
    if (!session) return 0;
    if (session.isPaused) {
      return Math.max(0, Number(session.remainingTime) || 0);
    }
    return Math.max(0, Number(session.endTime) - nowMs());
  }

  function setSession(session) {
    writeJson(STORAGE_KEYS.activeSession, session);
    window.dispatchEvent(new CustomEvent('focus-timer-updated', { detail: session }));
  }

  function isSessionActive() {
    const session = getSession();
    if (!session) return false;
    if (session.manualStop) return false;
    return getSessionRemainingMs(session) > 0;
  }

  function isSessionPaused() {
    const session = getSession();
    if (!session || session.manualStop) return false;
    return !!session.isPaused && getSessionRemainingMs(session) > 0;
  }

  function getRemainingTime() {
    const session = getSession();
    if (!session) {
      return {
        active: false,
        remainingMs: 0,
        remainingSeconds: 0,
        remainingMinutes: 0,
        isPaused: false,
        topic: '',
        durationMinutes: 0,
        session: null
      };
    }

    const remainingMs = getSessionRemainingMs(session);
    return {
      active: remainingMs > 0 && !session.manualStop,
      remainingMs,
      remainingSeconds: Math.floor(remainingMs / 1000),
      remainingMinutes: Math.ceil(remainingMs / 60000),
      isPaused: !!session.isPaused,
      topic: session.topic || '',
      durationMinutes: session.durationMinutes || Math.round((session.durationSeconds || 0) / 60),
      session
    };
  }

  function startFocusSession(topic, durationMinutes, metadata) {
    const existing = getSession();
    if (existing && !existing.manualStop && getSessionRemainingMs(existing) > 0) {
      return existing;
    }

    const minutes = Number(durationMinutes);
    const startTime = nowMs();
    const durationSeconds = Math.max(1, Math.floor(minutes * 60));
    const endTime = startTime + durationSeconds * 1000;

    const session = {
      id: 'focus-' + startTime,
      topic: String(topic || '').trim(),
      durationMinutes: minutes,
      durationSeconds,
      startTime,
      endTime,
      remainingTime: durationSeconds * 1000,
      isPaused: false,
      xpSeconds: 0,
      manualStop: false
    };

    if (metadata && typeof metadata === 'object') {
      if (metadata.subject) {
        session.subject = String(metadata.subject).trim();
      }
    }

    setSession(session);
    return session;
  }

  function pauseSession() {
    const session = getSession();
    if (!session || session.manualStop || session.isPaused) return session;

    const remainingMs = getSessionRemainingMs(session);
    if (remainingMs <= 0) {
      completeSessionIfNeeded();
      return null;
    }

    session.remainingTime = remainingMs;
    session.isPaused = true;
    setSession(session);
    window.dispatchEvent(new CustomEvent('focus-timer-paused', { detail: session }));
    return session;
  }

  function resumeSession() {
    const session = getSession();
    if (!session || session.manualStop || !session.isPaused) return session;

    const remainingMs = Math.max(0, Number(session.remainingTime) || 0);
    if (remainingMs <= 0) {
      completeSessionIfNeeded();
      return null;
    }

    const startTime = nowMs();
    session.startTime = startTime;
    session.endTime = startTime + remainingMs;
    session.isPaused = false;
    setSession(session);
    window.dispatchEvent(new CustomEvent('focus-timer-resumed', { detail: session }));
    return session;
  }

  function stopSession() {
    const session = getSession();
    if (session) {
      session.manualStop = true;
      setSession(session);
    }
    removeKey(STORAGE_KEYS.activeSession);
    window.dispatchEvent(new CustomEvent('focus-timer-stopped'));
  }

  function addXpSeconds(secondsToAdd) {
    const session = getSession();
    if (!session) return 0;
    const add = Math.max(0, Number(secondsToAdd) || 0);
    session.xpSeconds = Math.max(0, (session.xpSeconds || 0) + add);
    setSession(session);
    return session.xpSeconds;
  }

  function completeSessionIfNeeded() {
    const session = getSession();
    if (!session || session.manualStop) return null;

    if (getSessionRemainingMs(session) > 0) return null;

    const completion = {
      id: session.id,
      topic: session.topic,
      durationMinutes: session.durationMinutes,
      durationSeconds: session.durationSeconds,
      xpSeconds: session.xpSeconds || 0,
      completedAt: nowMs()
    };

    writeJson(STORAGE_KEYS.pendingCompletion, completion);
    removeKey(STORAGE_KEYS.activeSession);
    window.dispatchEvent(new CustomEvent('focus-session-completed', { detail: completion }));
    return completion;
  }

  function getPendingCompletion() {
    return readJson(STORAGE_KEYS.pendingCompletion);
  }

  function claimPendingCompletion() {
    const completion = getPendingCompletion();
    if (completion) {
      removeKey(STORAGE_KEYS.pendingCompletion);
    }
    return completion;
  }

  function formatSeconds(totalSeconds) {
    const seconds = Math.max(0, Number(totalSeconds) || 0);
    const mm = String(Math.floor(seconds / 60)).padStart(2, '0');
    const ss = String(seconds % 60).padStart(2, '0');
    return mm + ':' + ss;
  }

  window.FocusTimer = {
    startFocusSession,
    getRemainingTime,
    isSessionActive,
    isSessionPaused,
    pauseSession,
    resumeSession,
    stopSession,
    getSession,
    addXpSeconds,
    completeSessionIfNeeded,
    getPendingCompletion,
    claimPendingCompletion,
    formatSeconds
  };
})();
