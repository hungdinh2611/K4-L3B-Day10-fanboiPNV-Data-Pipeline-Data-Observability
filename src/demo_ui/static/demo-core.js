// Logic dung chung cho giao dien demo (index.html): goi API, theo doi job dang chay,
// tinh tien do pipeline, cac helper format.
(function (global) {
  'use strict';

  const STAGE_KEYS = ['baseline', 'corrupted', 'repaired'];
  const METRICS = [
    ['retrieval_hit_rate', 'Retrieval Hit Rate', 1],
    ['mean_token_f1', 'Token F1', 1],
    ['judge_accuracy', 'Judge Accuracy', 1],
    ['mean_judge_score', 'Judge Score', 5],
  ];
  const JOB_NAMES = { phase1: 'Phase 1', corruption: 'Phase 2' };

  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const num = (v) => typeof v === 'number' && Number.isFinite(v);
  const fmt = (v, d = 2) => (num(v) ? v.toFixed(d) : '—');
  const pct = (v) => (num(v) ? (v * 100).toFixed(1) + '%' : '—');
  const cut = (s, n) => { s = String(s ?? ''); return s.length > n ? s.slice(0, n - 1) + '…' : s; };
  const freshnessOf = (st) => (st && (st.freshness || (st.quality && st.quality.freshness))) || null;
  const isFallbackJudge = (a) => String(a?.judge?.reasoning || '').startsWith('Fallback');
  const answerOk = (a) => !!a && a.retrieval_hit && num(a.token_f1) && a.token_f1 >= 0.5;

  async function api(path, body) {
    const init = body === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) };
    const res = await fetch(path, init);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || res.statusText);
    return data;
  }

  // Giong evaluation.metrics._token_f1: so khop tap token (lowercase, tach theo khoang trang).
  function tokenF1(reference, prediction) {
    const toks = (s) => new Set(String(s || '').toLowerCase().split(/\s+/).filter(Boolean));
    const ref = toks(reference), pred = toks(prediction);
    if (!ref.size || !pred.size) return 0;
    let overlap = 0;
    for (const t of pred) if (ref.has(t)) overlap += 1;
    if (!overlap) return 0;
    const p = overlap / pred.size, r = overlap / ref.size;
    return (2 * p * r) / (p + r);
  }

  // Tien do cua 1 track ('phase1' | 'corruption') tu log dang "[phase1] 3/6 ...".
  // Tra ve { done, active, error }: so buoc da xong, buoc dang chay, buoc loi (-1 = khong co).
  function trackProgress(state, key, total) {
    const job = state.job || {};
    const stages = state.stages || {};
    const hasArtifacts = key === 'phase1' ? !!stages.baseline?.metrics : !!stages.repaired?.metrics;
    const idle = { done: hasArtifacts ? total : 0, active: -1, error: -1 };
    if (!job.name) return idle;

    const prefix = '[' + key + ']';
    const re = /^\[(phase1|corruption)\] (\d+)\/(\d+)/gm;
    let step = 0, lastPrefix = null, m;
    while ((m = re.exec(job.log || ''))) {
      lastPrefix = '[' + m[1] + ']';
      if (lastPrefix === prefix) step = +m[2];
    }
    if (step === 0) {
      if (job.status === 'running' && job.name === key) return { done: 0, active: -1, error: -1 };
      if (job.status === 'error' && job.name === key) return { done: 0, active: -1, error: 0 };
      return idle;
    }
    if (job.status === 'running') {
      return lastPrefix === prefix ? { done: step - 1, active: step - 1, error: -1 } : { done: total, active: -1, error: -1 };
    }
    if (job.status === 'error' && lastPrefix === prefix) return { done: step - 1, active: -1, error: step - 1 };
    return { done: total, active: -1, error: -1 };
  }

  function describeJob(job) {
    if (!job || !job.name) return '—';
    const name = JOB_NAMES[job.name] || job.name;
    if (job.status === 'running') {
      const s = Math.max(0, Math.round((job.now || Date.now() / 1000) - job.started_at));
      const clock = String(Math.floor(s / 60)).padStart(2, '0') + ':' + String(s % 60).padStart(2, '0');
      return `⏳ ${name} đang chạy · ${clock}${job.use_llm ? ' · LLM thật' : ' · judge heuristic'}`;
    }
    if (job.status === 'done') return `✔ ${name} hoàn tất trong ${Math.round(job.finished_at - job.started_at)}s`;
    if (job.status === 'error') return `✖ ${name} lỗi: ${job.error}`;
    return '—';
  }

  function classifyLogLine(line) {
    if (/^\[phase1\]/.test(line)) return 'phase1';
    if (/^\[corruption\]/.test(line)) return 'corruption';
    if (/(Error|Traceback|Exception)/.test(line)) return 'error';
    if (/^(===|Retrieval|Mean|Judge|Quality|Freshness|Metric|Report)/.test(line)) return 'highlight';
    return '';
  }

  // Quan ly state + polling. hooks: render(state), renderJob(state), toast(msg, kind), jobFinished(job).
  function createController(hooks) {
    let state = null;
    let pollTimer = null;
    let lastStatus = null;

    const ctl = {
      get state() { return state; },
      async refresh() {
        try {
          state = await api('/api/state');
          lastStatus = state.job.status;
          hooks.render(state);
          if (state.job.status === 'running') poll();
        } catch (e) {
          hooks.toast('Không tải được dữ liệu: ' + e.message, 'error');
        }
      },
      async startJob(name, useLlm) {
        try {
          state.job = await api('/api/run/' + name, { use_llm: !!useLlm });
          lastStatus = 'running';
          hooks.renderJob(state);
          poll();
        } catch (e) {
          hooks.toast(e.message, 'error');
        }
      },
      ask(question) {
        return api('/api/ask', { question });
      },
    };

    function poll() {
      if (pollTimer) return;
      pollTimer = setInterval(async () => {
        let job;
        try { job = await api('/api/job'); } catch { return; }
        state.job = job;
        hooks.renderJob(state);
        if (job.status !== 'running') {
          clearInterval(pollTimer);
          pollTimer = null;
          if (lastStatus === 'running') hooks.jobFinished(job);
          await ctl.refresh();
        }
      }, 500);
    }

    return ctl;
  }

  // Doc/ghi tuy chon trong localStorage (co the bi chan -> bo qua).
  function bindStoredCheckbox(el, storageKey) {
    try { el.checked = localStorage.getItem(storageKey) === '1'; } catch { /* storage unavailable */ }
    el.addEventListener('change', () => {
      try { localStorage.setItem(storageKey, el.checked ? '1' : '0'); } catch { /* ignore */ }
    });
  }

  global.DemoCore = {
    STAGE_KEYS, METRICS, esc, num, fmt, pct, cut, freshnessOf, isFallbackJudge, answerOk,
    api, tokenF1, trackProgress, describeJob, classifyLogLine, createController, bindStoredCheckbox,
  };
})(window);
