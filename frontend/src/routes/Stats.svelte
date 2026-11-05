<script>
  import { onMount } from 'svelte'
  import { ChevronLeft, ChevronRight, Loader2, TrendingUp, TrendingDown, Scale } from 'lucide-svelte'
  import { api } from '../lib/api.js'
  import { user, toast } from '../lib/stores.js'
  import { fmtAmount } from '../lib/format.js'
  import Icon from '../components/Icon.svelte'
  import PieChart from '../components/PieChart.svelte'

  const PERIODS = [
    { id: 'month', label: 'Месяц' },
    { id: 'quarter', label: '3 месяца' },
    { id: 'half', label: 'Полгода' },
    { id: 'year', label: 'Год' }
  ]

  let period = 'month'
  let offset = 0
  let currency = $user.report_currency
  let data = null
  let prev = null
  let loading = true

  async function load() {
    loading = true
    try {
      const curReq = api.get(`/stats?period=${period}&offset=${offset}&currency=${currency}`)
      const prevReq = api.get(`/stats?period=${period}&offset=${offset - 1}&currency=${currency}`)
      data = await curReq
      prev = await prevReq
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      loading = false
    }
  }

  function delta(cur, prevAmount) {
    if (!prevAmount) return null
    return Math.round(((cur - prevAmount) / prevAmount) * 1000) / 10
  }
  function prevOf(id) {
    return prev?.by_category?.find((c) => c.id === id)?.amount
  }

  function setPeriod(p) { period = p; offset = 0; load() }
  function setCurrency(c) { currency = c; load() }
  function move(d) { offset += d; load() }

  $: pieData = (data?.by_category || []).map((c) => ({ value: c.amount, color: c.color, name: c.name }))
  $: maxUser = data ? Math.max(1, ...data.by_user.flatMap((u) => [u.income, u.expense])) : 1
  $: dIncome = data ? delta(data.income_total, prev?.income_total) : null
  $: dExpense = data ? delta(data.expense_total, prev?.expense_total) : null
  $: sv = data?.savings || null
  $: maxCum = sv ? Math.max(1, ...sv.series.map((p) => Math.abs(p.cumulative))) : 1

  onMount(load)
</script>

<div class="head fade-up">
  <h2>Статистика</h2>
  <div class="segmented">
    <button class:active={currency === 'BYN'} on:click={() => setCurrency('BYN')}>Br</button>
    <button class:active={currency === 'USD'} on:click={() => setCurrency('USD')}>$</button>
  </div>
</div>

<div class="segmented periods">
  {#each PERIODS as p}
    <button class:active={period === p.id} on:click={() => setPeriod(p.id)}>{p.label}</button>
  {/each}
</div>

<div class="nav">
  <button class="btn btn-ghost btn-icon" on:click={() => move(-1)}><ChevronLeft size={20} /></button>
  <span class="label">{data?.label || ''}</span>
  <button class="btn btn-ghost btn-icon" on:click={() => move(1)} disabled={offset >= 0}><ChevronRight size={20} /></button>
</div>

{#if loading}
  <div class="center"><Loader2 size={28} class="spin" /></div>
{:else if data}
  <div class="summary">
    <div class="card sum">
      <div class="row" style="gap:8px"><TrendingUp size={16} class="ic-pos" /><span class="dim" style="font-size:13px">Доходы</span></div>
      <div class="mono val pos">{fmtAmount(data.income_total, currency)}</div>
      {#if dIncome != null}
        <span class="delta" class:pos={dIncome >= 0} class:neg={dIncome < 0} title="к прошлому периоду">{dIncome > 0 ? '+' : ''}{dIncome}%</span>
      {/if}
    </div>
    <div class="card sum">
      <div class="row" style="gap:8px"><TrendingDown size={16} class="ic-neg" /><span class="dim" style="font-size:13px">Расходы</span></div>
      <div class="mono val neg">{fmtAmount(data.expense_total, currency)}</div>
      {#if dExpense != null}
        <span class="delta" class:neg={dExpense > 0} class:pos={dExpense < 0} title="к прошлому периоду">{dExpense > 0 ? '+' : ''}{dExpense}%</span>
      {/if}
    </div>
    <div class="card sum">
      <div class="row" style="gap:8px"><Scale size={16} /><span class="dim" style="font-size:13px">Остаток</span></div>
      <div class="mono val" class:pos={data.net >= 0} class:neg={data.net < 0}>{fmtAmount(data.net, currency)}</div>
    </div>
  </div>

  <div class="card block chart-block">
    <h3>Расходы по категориям</h3>
    {#if data.by_category.length === 0}
      <div class="empty">Нет расходов за этот период</div>
    {:else}
      <div class="chart-row">
        <PieChart data={pieData} {currency} />
        <div class="legend">
          {#each data.by_category as c}
            {@const d = delta(c.amount, prevOf(c.id))}
            <div class="leg">
              <span class="chip" style="background:{c.color}"><Icon name={c.icon} size={13} color="#fff" /></span>
              <span class="grow leg-name">{c.name}</span>
              <span class="leg-pct mono">{c.percent}%</span>
              <div class="leg-right">
                <span class="mono leg-amt">{fmtAmount(c.amount, currency)}</span>
                {#if d != null}
                  <span class="delta" class:neg={d > 0} class:pos={d < 0} title="к прошлому периоду">{d > 0 ? '+' : ''}{d}%</span>
                {/if}
              </div>
            </div>
          {/each}
        </div>
      </div>
    {/if}
  </div>

  {#if sv}
    <div class="card block">
      <h3>Накопления в копилках</h3>

      <div class="sv-summary">
        <div class="sv-kpi">
          <span class="dim">Накоплено сейчас</span>
          <span class="mono val">{fmtAmount(sv.total_balance, currency)}</span>
        </div>
        {#if sv.total_goal > 0}
          <div class="sv-kpi">
            <span class="dim">Общая цель</span>
            <span class="mono val">{fmtAmount(sv.total_goal, currency)}</span>
          </div>
        {/if}
        <div class="sv-kpi">
          <span class="dim">За {data.label}</span>
          <span class="mono val" class:pos={sv.period_change >= 0} class:neg={sv.period_change < 0}>
            {fmtAmount(sv.period_change, currency, { sign: true })}
          </span>
        </div>
      </div>

      {#if sv.progress != null}
        <div class="goal-line">
          <div class="bar-track big"><div class="bar pos-bar" style="width:{sv.progress}%"></div></div>
          <span class="faint" style="font-size:12px">{sv.progress}% от общей цели</span>
        </div>
      {/if}

      {#if sv.series.length >= 2}
        <div class="dyn-title faint">Динамика накоплений</div>
        <div class="dyn">
          {#each sv.series as pt}
            <div class="dyn-col" title="Накоплено {fmtAmount(pt.cumulative, currency)} · за месяц {fmtAmount(pt.net, currency, { sign: true })}">
              <div class="dyn-bar-wrap">
                <div class="dyn-bar" style="height:{Math.max(2, (Math.abs(pt.cumulative) / maxCum) * 100)}%"></div>
              </div>
              <span class="dyn-lbl">{pt.label}</span>
            </div>
          {/each}
        </div>
      {/if}

      <div class="sv-list">
        {#each sv.items as it}
          <div class="sv-item">
            <span class="chip" style="background:{it.color}"><Icon name={it.icon} size={14} color="#fff" /></span>
            <div class="grow" style="min-width:0">
              <div class="between">
                <span class="sv-name">{it.name}</span>
                <span class="mono sv-bal">{fmtAmount(it.balance, currency)}</span>
              </div>
              {#if it.progress != null}
                <div class="sv-prog">
                  <div class="bar-track"><div class="bar" style="width:{it.progress}%;background:{it.color}"></div></div>
                  <span class="faint" style="font-size:11px">{it.progress}% · цель {fmtAmount(it.goal_report, currency)}</span>
                </div>
              {/if}
            </div>
            <span class="mono sv-chg" class:pos={it.period_change >= 0} class:neg={it.period_change < 0}>
              {fmtAmount(it.period_change, currency, { sign: true })}
            </span>
          </div>
        {/each}
      </div>
    </div>
  {/if}

  <div class="card block">
    <h3>По участникам</h3>
    <div class="users">
      {#each data.by_user as u}
        <div class="urow">
          <div class="between" style="margin-bottom:8px">
            <span style="font-weight:600">{u.name}</span>
            <span class="faint" style="font-size:12px">доход {fmtAmount(u.income, currency)} · расход {fmtAmount(u.expense, currency)}</span>
          </div>
          <div class="bars">
            <div class="bar-track"><div class="bar pos-bar" style="width:{(u.income / maxUser) * 100}%"></div></div>
            <div class="bar-track"><div class="bar neg-bar" style="width:{(u.expense / maxUser) * 100}%"></div></div>
          </div>
        </div>
      {/each}
      {#if data.by_user.length === 0}<div class="empty">Нет данных</div>{/if}
    </div>
  </div>

  <p class="faint note">Суммы пересчитаны в {currency} по текущему курсу НБРБ{data.rate ? ` (1$ = ${data.rate} Br)` : ''}.</p>
{/if}

<style>
  .head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
  .head h2 { font-size: 22px; font-weight: 800; }
  .periods { width: 100%; margin-bottom: 14px; }
  .periods button { flex: 1; }
  .nav { display: flex; align-items: center; justify-content: center; gap: 14px; margin-bottom: 18px; }
  .nav .label { font-weight: 700; font-size: 16px; min-width: 160px; text-align: center; }
  .center { display: grid; place-items: center; height: 40vh; color: var(--accent); }

  .summary { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 16px; }
  .sum { padding: 14px; display: flex; flex-direction: column; gap: 6px; min-width: 0; }
  .sum .val { font-size: 17px; font-weight: 800; letter-spacing: -0.4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  @media (max-width: 520px) {
    .summary { grid-template-columns: 1fr 1fr; }
    .sum:last-child { grid-column: 1 / -1; }
  }
  .sum .row { min-width: 0; }
  .sum .row span { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  :global(.ic-pos) { color: var(--pos); }
  :global(.ic-neg) { color: var(--neg); }

  .block { padding: 18px; margin-bottom: 16px; }
  .block h3 { font-size: 15px; font-weight: 700; margin-bottom: 16px; }
  /* Диаграмма сверху, список под ней: сбоку он жался в колонку,
     а диаграмма висела в пустоте напротив двух десятков строк. */
  .chart-row { display: flex; flex-direction: column; align-items: center; gap: 20px; }
  .legend { width: 100%; display: flex; flex-direction: column; }
  .leg {
    display: flex; align-items: center; gap: 12px;
    padding: 9px 4px; border-top: 1px solid var(--border);
  }
  .leg:first-child { border-top: none; }
  .chip { width: 28px; height: 28px; border-radius: 9px; display: grid; place-items: center; flex-shrink: 0; }
  .leg-name { font-size: 14px; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .leg-pct {
    font-size: 12px; font-weight: 700; color: var(--text-dim);
    background: var(--surface-strong); padding: 3px 8px; border-radius: 999px; flex-shrink: 0;
  }
  .leg-amt { font-size: 14px; font-weight: 700; }
  .leg-right { display: flex; flex-direction: column; align-items: flex-end; gap: 1px; flex-shrink: 0; min-width: 96px; }
  .delta { font-size: 11px; font-weight: 700; white-space: nowrap; }

  .users { display: flex; flex-direction: column; gap: 16px; }
  .bars { display: flex; flex-direction: column; gap: 6px; }
  .bar-track { height: 8px; background: var(--surface-strong); border-radius: 999px; overflow: hidden; }
  .bar { height: 100%; border-radius: 999px; transition: width 0.5s cubic-bezier(0.4,0,0.2,1); }
  .pos-bar { background: linear-gradient(90deg, #22c55e, #10b981); }
  .neg-bar { background: linear-gradient(90deg, #f43f5e, #f97316); }

  .empty { color: var(--text-faint); font-size: 14px; text-align: center; padding: 16px; }
  .note { font-size: 12px; text-align: center; margin-top: 4px; }

  .sv-summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(110px, 1fr)); gap: 12px; margin-bottom: 14px; }
  .sv-kpi { display: flex; flex-direction: column; gap: 4px; }
  .sv-kpi .dim { font-size: 12px; }
  .sv-kpi .val { font-size: 17px; font-weight: 800; letter-spacing: -0.4px; }
  .goal-line { display: flex; flex-direction: column; gap: 6px; margin-bottom: 18px; }
  .bar-track.big { height: 12px; }

  .dyn-title { font-size: 12px; margin-bottom: 10px; }
  .dyn { display: flex; align-items: flex-end; gap: 6px; height: 120px; margin-bottom: 20px; }
  .dyn-col { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 6px; height: 100%; min-width: 0; }
  .dyn-bar-wrap { flex: 1; width: 100%; display: flex; align-items: flex-end; justify-content: center; }
  .dyn-bar { width: 70%; max-width: 34px; min-height: 2px; border-radius: 6px 6px 0 0; background: var(--grad); transition: height 0.5s cubic-bezier(0.4,0,0.2,1); }
  .dyn-lbl { font-size: 10px; color: var(--text-faint); white-space: nowrap; }

  .sv-list { display: flex; flex-direction: column; gap: 14px; }
  .sv-item { display: flex; align-items: center; gap: 12px; }
  .sv-name { font-size: 14px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .sv-bal { font-size: 14px; font-weight: 700; }
  .sv-prog { display: flex; flex-direction: column; gap: 4px; margin-top: 6px; }
  .sv-chg { font-size: 13px; font-weight: 700; white-space: nowrap; flex-shrink: 0; }
</style>
