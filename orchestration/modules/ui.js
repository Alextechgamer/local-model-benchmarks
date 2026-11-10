function bindUI(api) {
  'use strict';

  var $ = function (id) { return document.getElementById(id); };

  var el = {
    loading: $('loading'),
    title: $('title'),
    panel: $('panel'),
    panelToggle: $('panel-toggle'),
    time: $('time'),
    timeVal: $('time-val'),
    play: $('play'),
    speed: $('speed'),
    speedVal: $('speed-val'),
    petals: $('petals'),
    petalsVal: $('petals-val'),
    wind: $('wind'),
    windVal: $('wind-val'),
    autorotate: $('autorotate'),
    shadows: $('shadows'),
    fireflies: $('fireflies'),
    water: $('water'),
    wireframe: $('wireframe'),
    presets: document.querySelectorAll('[data-preset]'),
    regen: $('regen'),
    reset: $('reset'),
    help: $('help'),
    helpTip: $('help-tip'),
    rVoxels: $('r-voxels'),
    rFps: $('r-fps'),
    rTime: $('r-time'),
    toast: $('toast')
  };

  var PRESET_ORDER = ['Overview', 'Pagoda', 'Pond', 'Torii', 'Blossoms'];
  var STATUS_KEYS = ['voxels', 'fps', 'time'];

  var on = function (node, type, fn, opts) {
    if (node) node.addEventListener(type, fn, opts || false);
  };

  var call = function (name) {
    try {
      if (api && typeof api[name] === 'function') {
        var out = api[name].apply(api, Array.prototype.slice.call(arguments, 1));
        return out;
      }
    } catch (err) {
      if (window.console && console.warn) console.warn('[ui] api.' + name + ' failed:', err);
    }
    return undefined;
  };

  /* ------------------------------------------------------------------ *
   * small helpers
   * ------------------------------------------------------------------ */

  var pad2 = function (n) { return (n < 10 ? '0' : '') + n; };

  var clamp = function (v, a, b) { return v < a ? a : (v > b ? b : v); };

  var num = function (v, fallback) {
    var n = parseFloat(v);
    return isFinite(n) ? n : fallback;
  };

  var fmtHour = function (h) {
    if (!isFinite(h)) return '--:--';
    var wrapped = ((h % 24) + 24) % 24;
    var hh = Math.floor(wrapped);
    var mm = Math.floor((wrapped - hh) * 60 + 0.0001);
    if (mm >= 60) { mm -= 60; hh = (hh + 1) % 24; }
    return pad2(hh) + ':' + pad2(mm);
  };

  var fmtClockLabel = function (h) {
    var hh = Math.floor(clamp(h, 0, 24));
    var mins = Math.round((clamp(h, 0, 24) - hh) * 60);
    if (mins === 60) { mins = 0; hh = (hh + 1) % 24; }
    return pad2(hh) + ':' + pad2(mins);
  };

  /* ------------------------------------------------------------------ *
   * toast
   * ------------------------------------------------------------------ */

  var toastTimer = 0;

  function toast(msg) {
    if (!el.toast) return;
    el.toast.textContent = msg;
    el.toast.classList.add('show');
    if (toastTimer) window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(function () {
      el.toast.classList.remove('show');
    }, 1700);
  }

  /* ------------------------------------------------------------------ *
   * loading overlay
   * ------------------------------------------------------------------ */

  if (el.loading) {
    el.loading.classList.add('hide');
    window.setTimeout(function () {
      el.loading.style.display = 'none';
    }, 900);
  }

  /* ------------------------------------------------------------------ *
   * panel collapse
   * ------------------------------------------------------------------ */

  var collapsed = false;

  function setCollapsed(next) {
    collapsed = !!next;
    if (el.panel) el.panel.classList.toggle('collapsed', collapsed);
    if (el.panelToggle) el.panelToggle.classList.toggle('show', collapsed);
  }

  on(el.panelToggle, 'click', function () { setCollapsed(false); });

  /* ------------------------------------------------------------------ *
   * help tooltip
   * ------------------------------------------------------------------ */

  var helpOpen = false;
  var helpHideTimer = 0;

  function setHelp(next) {
    helpOpen = !!next;
    if (helpHideTimer) { window.clearTimeout(helpHideTimer); helpHideTimer = 0; }
    if (el.helpTip) el.helpTip.classList.toggle('show', helpOpen);
    if (el.help) el.help.classList.toggle('active', helpOpen);
  }

  on(el.help, 'click', function (e) {
    e.preventDefault();
    e.stopPropagation();
    setHelp(!helpOpen);
  });
  on(el.help, 'mouseenter', function () { setHelp(true); });
  on(el.help, 'mouseleave', function () {
    helpHideTimer = window.setTimeout(function () {
      if (el.helpTip && !el.helpTip.matches(':hover')) setHelp(false);
    }, 260);
  });
  on(el.helpTip, 'mouseenter', function () {
    if (helpHideTimer) { window.clearTimeout(helpHideTimer); helpHideTimer = 0; }
  });
  on(el.helpTip, 'mouseleave', function () { setHelp(false); });
  on(document, 'pointerdown', function (e) {
    if (!helpOpen) return;
    var t = e.target;
    if (t && t !== el.help && !(el.helpTip && el.helpTip.contains(t)) && !(el.help && el.help.contains(t))) {
      setHelp(false);
    }
  });

  /* ------------------------------------------------------------------ *
   * time
   * ------------------------------------------------------------------ */

  var timeDirty = false;

  function syncTimeSlider() {
    var h = num(call('getTime'), num(el.time && el.time.value, 8));
    if (el.time) el.time.value = String(h);
    if (el.timeVal) el.timeVal.textContent = fmtHour(h);
    if (el.rTime) el.rTime.textContent = fmtHour(h);
  }

  on(el.time, 'input', function () {
    var h = num(el.time.value, 8);
    call('setTime', h);
    timeDirty = false;
    syncTimeSlider();
  });

  /* ------------------------------------------------------------------ *
   * play / pause
   * ------------------------------------------------------------------ */

  var playing = true;

  function syncPlay() {
    if (el.play) {
      el.play.textContent = playing ? 'Pause' : 'Play';
      el.play.classList.toggle('active', playing);
    }
  }

  on(el.play, 'click', function () {
    playing = !playing;
    call('setPlaying', playing);
    syncPlay();
    toast(playing ? 'Day cycle running' : 'Day cycle paused');
  });

  /* ------------------------------------------------------------------ *
   * speed / petals / wind
   * ------------------------------------------------------------------ */

  on(el.speed, 'input', function () {
    var v = num(el.speed.value, 1);
    call('setSpeed', v);
    if (el.speedVal) el.speedVal.textContent = v.toFixed(1) + '\u00d7/s';
  });

  on(el.petals, 'input', function () {
    var v = Math.round(clamp(num(el.petals.value, 900), 0, 1500));
    call('setPetalDensity', v);
    if (el.petalsVal) el.petalsVal.textContent = String(v);
  });

  on(el.wind, 'input', function () {
    var v = clamp(num(el.wind.value, 1), 0, 3);
    call('setWind', v);
    if (el.windVal) el.windVal.textContent = v.toFixed(1);
  });

  /* ------------------------------------------------------------------ *
   * checkboxes
   * ------------------------------------------------------------------ */

  on(el.autorotate, 'change', function () {
    call('setAutoRotate', !!el.autorotate.checked);
  });

  on(el.shadows, 'change', function () {
    call('setShadows', !!el.shadows.checked);
  });

  on(el.fireflies, 'change', function () {
    call('setFireflies', !!el.fireflies.checked);
  });

  on(el.water, 'change', function () {
    call('setWaterAnim', !!el.water.checked);
  });

  on(el.wireframe, 'change', function () {
    call('setWireframe', !!el.wireframe.checked);
  });

  /* ------------------------------------------------------------------ *
   * presets
   * ------------------------------------------------------------------ */

  function goPreset(name) {
    call('goPreset', name);
    for (var i = 0; i < el.presets.length; i++) {
      el.presets[i].classList.toggle('active', el.presets[i].getAttribute('data-preset') === name);
    }
    toast(name);
  }

  for (var i = 0; i < el.presets.length; i++) {
    (function (btn) {
      on(btn, 'click', function () { goPreset(btn.getAttribute('data-preset')); });
    })(el.presets[i]);
  }

  var nightJumps = document.querySelectorAll('.night-jump');
  for (var n = 0; n < nightJumps.length; n++) {
    on(nightJumps[n], 'click', function () {
      call('toggleNight');
      syncTimeSlider();
      toast('Time jumped');
    });
  }

  on(el.reset, 'click', function () {
    call('resetView');
    for (var p = 0; p < el.presets.length; p++) {
      if (el.presets[p].getAttribute('data-preset') === 'Overview') el.presets[p].classList.add('active');
      else el.presets[p].classList.remove('active');
    }
    toast('View reset');
  });

  /* ------------------------------------------------------------------ *
   * regenerate
   * ------------------------------------------------------------------ */

  on(el.regen, 'click', function () {
    var seed = Math.floor(Math.random() * 1e9);
    var res = call('regenerate', seed);
    if (res && typeof res.then === 'function') {
      toast('Rebuilding\u2026');
      res.then(function (g) {
        syncStats(true);
        if (g && g.seed != null) toast('New garden \u00b7 seed ' + g.seed);
        else toast('New garden built');
      }, function () {
        toast('New garden built');
      });
    } else {
      syncStats(true);
      toast('New garden \u00b7 seed ' + seed);
    }
  });

  /* ------------------------------------------------------------------ *
   * keyboard shortcuts
   * ------------------------------------------------------------------ */

  function isTyping(t) {
    if (!t || !t.tagName) return false;
    var tag = t.tagName.toLowerCase();
    return t.isContentEditable === true ||
      tag === 'input' || tag === 'textarea' || tag === 'select' || tag === 'option';
  }

  on(window, 'keydown', function (e) {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    if (isTyping(e.target)) return;

    var key = e.key;
    var code = e.code;

    if (key === ' ' || code === 'Space' || key === 'Spacebar') {
      e.preventDefault();
      call('toggleAutoRotate');
      var ar = call('getAutoRotate');
      if (el.autorotate) el.autorotate.checked = isFinite(ar) ? !!ar : !el.autorotate.checked;
      return;
    }

    if (key === 'n' || key === 'N') {
      e.preventDefault();
      call('toggleNight');
      syncTimeSlider();
      toast('Time jumped');
      return;
    }

    var digit = null;
    if (key && key.length === 1 && key >= '1' && key <= '5') digit = parseInt(key, 10);
    else if (code && /^Digit[1-5]$/.test(code)) digit = parseInt(code.slice(5), 10);
    else if (code && /^Numpad[1-5]$/.test(code)) digit = parseInt(code.slice(6), 10);

    if (digit !== null) {
      e.preventDefault();
      goPreset(PRESET_ORDER[digit - 1]);
    }
  });

  /* ------------------------------------------------------------------ *
   * readouts ~4 Hz
   * ------------------------------------------------------------------ */

  function syncStats(force) {
    var s = null;
    try { s = call('stats'); } catch (err) { s = null; }
    if (!s) return;

    if (el.rVoxels) {
      var v = num(s[STATUS_KEYS[0]], 0);
      el.rVoxels.textContent = v.toLocaleString ? v.toLocaleString() : String(Math.round(v));
    }
    if (el.rFps) el.rFps.textContent = String(Math.round(num(s[STATUS_KEYS[1]], 0)));
    if (el.rTime) el.rTime.textContent = fmtHour(num(s[STATUS_KEYS[2]], num(el.time && el.time.value, 8)));

    var live = num(call('getTime'), NaN);
    if (force || !isFinite(live)) {
      if (isFinite(live)) syncTimeSlider();
    } else if (!timeDirty) {
      if (el.time) el.time.value = String(live);
      if (el.timeVal) el.timeVal.textContent = fmtClockLabel(live);
    }
  }

  window.setInterval(function () { syncStats(false); }, 250);

  /* ------------------------------------------------------------------ *
   * boot
   * ------------------------------------------------------------------ */

  function boot() {
    var h = num(call('getTime'), num(el.time && el.time.value, 8));
    if (el.time) el.time.value = String(h);
    if (el.timeVal) el.timeVal.textContent = fmtHour(h);
    if (el.rTime) el.rTime.textContent = fmtHour(h);

    if (el.speed) {
      el.speed.value = String(num(el.speed.value, 1));
      if (el.speedVal) el.speedVal.textContent = num(el.speed.value, 1).toFixed(1) + '\u00d7/s';
    }
    if (el.petals) {
      var p = Math.round(clamp(num(el.petals.value, 900), 0, 1500));
      el.petals.value = String(p);
      if (el.petalsVal) el.petalsVal.textContent = String(p);
    }
    if (el.wind) {
      var w = clamp(num(el.wind.value, 1), 0, 3);
      el.wind.value = String(w);
      if (el.windVal) el.windVal.textContent = w.toFixed(1);
    }

    playing = true;
    syncPlay();
    syncStats(true);
  }

  if (document.readyState === 'loading') {
    on(document, 'DOMContentLoaded', boot);
  } else {
    boot();
  }

  /* keyboard Space must not re-trigger a focused button */
  on(document, 'keyup', function (e) {
    var key = e.key;
    if (key === ' ' || e.code === 'Space') {
      if (e.target && e.target.tagName && e.target.tagName.toLowerCase() === 'button') {
        e.target.blur();
      }
    }
  });

  return {
    setPlaying: function (v) { playing = !!v; syncPlay(); },
    toast: toast,
    refresh: function () { syncStats(true); }
  };
}