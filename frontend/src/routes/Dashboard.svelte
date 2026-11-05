<script>
  import { onMount } from 'svelte'
  import { Plus, Pencil, RefreshCw, TrendingUp, TrendingDown, ArrowLeftRight, HandCoins, Loader2, ChevronLeft, ChevronRight, History, Archive } from 'lucide-svelte'

  import { api } from '../lib/api.js'
  import { user, toast } from '../lib/stores.js'
  import { fmtAmount, fmtDate, convertAmount, payDayHint } from '../lib/format.js'
  import Icon from '../components/Icon.svelte'
  import Avatar from '../components/Avatar.svelte'
  import AccountCard from '../components/AccountCard.svelte'
  import AccountModal from '../components/AccountModal.svelte'
  import CategoryModal from '../components/CategoryModal.svelte'
  import OperationModal from '../components/OperationModal.svelte'
  import DebtModal from '../components/DebtModal.svelte'
  import DebtPaymentModal from '../components/DebtPaymentModal.svelte'
  import CategoryHistoryModal from '../components/CategoryHistoryModal.svelte'

  let accounts = []
  let categories = []
  let debts = []
  let archivedDebts = []
  let showArchive = false
  let users = []
  let txs = []
  let q = ''
  let page = 0
  const PER_PAGE = 15
  let rate = null
  let reportCurrency = 'BYN'
  let loading = true
  let refreshingRate = false

  // Срез по месяцам: 0 — текущий, -1 — прошлый, +1 — следующий.
  let monthOffset = 0
  let monthLabel = ''
  let monthFrom = ''
  let monthTo = ''
  let monthIncome = 0
  let monthExpense = 0
  let catSpent = {}   // { [categoryId]: сумма трат за месяц (в валюте отчёта) }
  let catPct = {}     // { [categoryId]: % от прихода за месяц }

  let opModal = null        // { initial?, tx? }
  let accModal = null       // { account? , kind? }
  let catModal = null       // { category? }
  let debtModal = null      // { debt? }
  let payModal = null       // { debt }
  let catHistory = null     // { category }

  $: incomeAccs = accounts.filter((a) => a.kind === 'income')
  $: spendAccs = accounts.filter((a) => a.kind === 'card' || a.kind === 'cash')
  $: savingsAccs = accounts.filter((a) => a.kind === 'savings')
  $: total = accounts.reduce((s, a) => s + (a.balance_report || 0), 0)
  $: debtsTotal = debts.reduce((s, d) => s + (d.remaining_report || 0), 0)
  $: netWorth = total - debtsTotal
  $: visibleTxs = txs.filter((t) => {
    const s = q.trim().toLowerCase()
    if (!s) return true
    return [t.note, t.account_name, t.dest_account_name, t.category_name, t.debt_name, t.created_by_name]
      .some((v) => (v || '').toLowerCase().includes(s))
  })
  $: monthLeft = monthIncome - monthExpense
  $: pageCount = Math.max(1, Math.ceil(visibleTxs.length / PER_PAGE))
  $: if (page > pageCount - 1) page = pageCount - 1
  $: pageTxs = visibleTxs.slice(page * PER_PAGE, page * PER_PAGE + PER_PAGE)

  async function load() {
    loading = true
    try {
      const [acc, cats, dbt, arc, us, st] = await Promise.all([
        api.get(`/accounts?month_offset=${monthOffset}`),
        api.get('/categories'),
        api.get(`/debts?month_offset=${monthOffset}`),
        api.get('/debts?archived=true'),
        api.get('/profile/users'),
        api.get(`/stats?period=month&offset=${monthOffset}`)
      ])
      accounts = acc.accounts
      rate = acc.rate
      reportCurrency = acc.report_currency
      categories = cats
      debts = dbt.debts
      archivedDebts = arc.debts
      users = us

      // Помесячная сводка по категориям и приходу
      monthLabel = st.label
      monthFrom = st.date_from
      monthTo = st.date_to
      monthIncome = st.income_total
      monthExpense = st.expense_total
      const spent = {}, pct = {}
      for (const row of st.by_category) {
        if (typeof row.id !== 'number') continue   // пропускаем долги и «без категории»
        spent[row.id] = row.amount
        pct[row.id] = st.income_total > 0 ? Math.round((row.amount / st.income_total) * 1000) / 10 : 0
      }
      catSpent = spent
      catPct = pct

      // Операции только за выбранный месяц
      txs = await api.get(`/transactions?date_from=${st.date_from}&date_to=${st.date_to}&limit=500`)
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      loading = false
    }
  }

  function changeMonth(delta) {
    monthOffset += delta
    page = 0
    load()
  }

  async function refreshRate() {
    refreshingRate = true
    try {
      const r = await api.post('/rates/refresh')
      rate = r.usd_byn
      toast(`Курс обновлён: 1$ = ${r.usd_byn} Br`, 'success')
      await load()
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      refreshingRate = false
    }
  }

  function onSaved() {
    opModal = accModal = catModal = debtModal = payModal = null
    load()
  }

  const greeting = () => {
    const h = new Date().getHours()
    if (h < 6) return 'Доброй ночи'
    if (h < 12) return 'Доброе утро'
    if (h < 18) return 'Добрый день'
    return 'Добрый вечер'
  }

  const txMeta = {
    income: { icon: TrendingUp, cls: 'pos', sign: '+' },
    expense: { icon: TrendingDown, cls: 'neg', sign: '−' },
    transfer: { icon: ArrowLeftRight, cls: 'dim', sign: '' },
    debt_payment: { icon: HandCoins, cls: 'neg', sign: '−' }
  }

  const KIND_LABEL = { debt: 'Долг', credit: 'Кредит', leasing: 'Лизинг' }

  async function setArchived(debt, archived) {
    try {
      await api.post(`/debts/${debt.id}/archive?archived=${archived}`)
      toast(archived ? 'Убрано в архив' : 'Возвращено из архива', 'success')
      load()
    } catch (e) {
      toast(e.message, 'error')
    }
  }

  async function handleTxClick(t) {
    if (t.type === 'debt_payment') {
      if (confirm('Удалить этот платёж по долгу? Остаток долга будет восстановлен.')) {
        try {
          await api.del(`/transactions/${t.id}`)
          toast('Платёж удалён', 'success')
          load()
        } catch (e) {
          toast(e.message, 'error')
        }
      }
      return
    }
    opModal = { tx: t }
  }

  onMount(load)
</script>

{#if loading}
  <div class="center"><Loader2 size={30} class="spin" /></div>
{:else}
  <!-- Header -->
  <div class="card hero fade-up">
    <div class="between">
      <div class="row">
        <Avatar name={$user.avatar} size={46} />
        <div>
          <div class="dim" style="font-size:13px">{greeting()},</div>
          <div style="font-size:17px;font-weight:700">{$user.display_name}</div>
        </div>
      </div>
      <button class="rate" on:click={refreshRate} disabled={refreshingRate} title="Обновить курс НБРБ">
        {#if refreshingRate}<Loader2 size={14} class="spin" />{:else}<RefreshCw size={14} />{/if}
        {rate ? `1$ = ${rate} Br` : 'нет курса'}
      </button>
    </div>
    <div class="month-nav">
      <button class="mnav-btn" on:click={() => changeMonth(-1)} aria-label="Предыдущий месяц"><ChevronLeft size={18} /></button>
      <div class="mnav-label">
        {monthLabel}
        {#if monthOffset === 0}<span class="mnav-tag">текущий</span>{/if}
      </div>
      <button class="mnav-btn" on:click={() => changeMonth(1)} aria-label="Следующий месяц"><ChevronRight size={18} /></button>
    </div>
    <div class="total">
      <span class="dim" style="font-size:13px">
        {monthOffset === 0 ? 'Всего на счетах' : 'На счетах на конец месяца'}
      </span>
      <div class="total-val mono">{fmtAmount(total, reportCurrency)}</div>
      <div class="flows">
        <div class="flow-item">
          <span class="faint">Приход за месяц</span>
          <span class="mono pos">{fmtAmount(monthIncome, reportCurrency)}</span>
        </div>
        <div class="nw-sep"></div>
        <div class="flow-item">
          <span class="faint">Расход за месяц</span>
          <span class="mono neg">−{fmtAmount(monthExpense, reportCurrency).replace('+', '')}</span>
        </div>
        <div class="nw-sep"></div>
        <div class="flow-item">
          <span class="faint">Осталось</span>
          <span class="mono" class:pos={monthLeft >= 0} class:neg={monthLeft < 0}>{fmtAmount(monthLeft, reportCurrency)}</span>
        </div>
      </div>
      {#if debts.length}
        <div class="networth">
          <div class="nw-item">
            <span class="faint">Долги</span>
            <span class="mono neg">−{fmtAmount(debtsTotal, reportCurrency).replace('+', '')}</span>
          </div>
          <div class="nw-sep"></div>
          <div class="nw-item">
            <span class="faint">Чистый капитал</span>
            <span class="mono" class:pos={netWorth >= 0} class:neg={netWorth < 0}>{fmtAmount(netWorth, reportCurrency)}</span>
          </div>
        </div>
      {/if}
    </div>
  </div>

  <!-- Доходы -->
  <section>
    <div class="sec-head">
      <h3>Источники дохода</h3>
      <button class="btn btn-ghost btn-icon" on:click={() => (accModal = { kind: 'income' })}><Plus size={18} /></button>
    </div>
    <div class="grid2">
      {#each incomeAccs as a (a.id)}
        <AccountCard account={a} {reportCurrency} on:click={() => (accModal = { account: a })} />
      {/each}
      {#if incomeAccs.length === 0}<div class="empty">Нет источников дохода</div>{/if}
    </div>
  </section>

  <!-- Счета -->
  <section>
    <div class="sec-head">
      <h3>Счета</h3>
      <button class="btn btn-ghost btn-icon" on:click={() => (accModal = { kind: 'card' })}><Plus size={18} /></button>
    </div>
    <div class="grid2">
      {#each spendAccs as a (a.id)}
        <AccountCard account={a} {reportCurrency} on:click={() => (accModal = { account: a })} />
      {/each}
      {#if spendAccs.length === 0}<div class="empty">Нет счетов</div>{/if}
    </div>
  </section>

  <!-- Копилка -->
  <section>
    <div class="sec-head">
      <h3>Копилка</h3>
      <button class="btn btn-ghost btn-icon" on:click={() => (accModal = { kind: 'savings' })}><Plus size={18} /></button>
    </div>
    {#if savingsAccs.length === 0}
      <div class="empty">Копилка пуста</div>
    {:else}
      <div class="debts">
        {#each savingsAccs as a (a.id)}
          {@const goal = a.goal_amount || 0}
          {@const pct = goal > 0 ? Math.min(100, Math.round((a.balance / goal) * 1000) / 10) : 0}
          {@const reached = goal > 0 && a.balance >= goal}
          <button class="debt card sv" on:click={() => (accModal = { account: a })}>
            <div class="debt-top">
              <div class="icon-badge" style="background:{a.color}"><Icon name={a.icon} size={20} /></div>
              <div class="grow" style="min-width:0">
                <div class="debt-name">{a.name}</div>
                <div class="faint debt-sub">{goal > 0 ? 'Цель по сумме' : 'Копилка'}</div>
              </div>
              <span class="cat-edit static" aria-hidden="true"><Pencil size={13} /></span>
            </div>

            {#if goal > 0}
              <div class="debt-bar-row">
                <div class="bar-track"><div class="bar" style="width:{pct}%;background:{a.color}"></div></div>
                <span class="faint" style="font-size:12px">{pct}%</span>
              </div>
            {/if}

            <div class="between debt-nums">
              <div>
                <div class="faint" style="font-size:11px">Накоплено</div>
                <div class="mono" style="font-weight:800;font-size:17px" class:neg={a.balance < 0}>{fmtAmount(a.balance, a.currency)}</div>
              </div>
              <div style="text-align:right">
                {#if goal > 0}
                  <div class="faint" style="font-size:11px">цель {fmtAmount(goal, a.currency)}</div>
                  {#if reached}<div class="pos" style="font-size:12px;font-weight:700">Цель достигнута 🎉</div>{/if}
                {:else if a.currency !== reportCurrency && a.balance_report != null}
                  <div class="faint" style="font-size:11px">{fmtAmount(a.balance_report, reportCurrency)}</div>
                {/if}
              </div>
            </div>
          </button>
        {/each}
      </div>
    {/if}
  </section>

  <!-- Долги / кредиты / лизинги -->
  <section>
    <div class="sec-head">
      <h3>Долги, кредиты, лизинги</h3>
      <div class="row" style="gap:8px">
        {#if archivedDebts.length}
          <button class="arch-toggle" on:click={() => (showArchive = !showArchive)}>
            <Archive size={13} /> Архив · {archivedDebts.length}
          </button>
        {/if}
        <button class="btn btn-ghost btn-icon" on:click={() => (debtModal = {})}><Plus size={18} /></button>
      </div>
    </div>
    {#if debts.length === 0}
      <div class="empty">Нет активных обязательств</div>
    {:else}
      <div class="debts">
        {#each debts as d (d.id)}
          <div class="debt card">
            <div class="debt-top">
              <div class="icon-badge" style="background:{d.color}"><Icon name={d.icon} size={20} /></div>
              <div class="grow" style="min-width:0">
                <div class="debt-name">{d.name}</div>
                <div class="faint debt-sub">{KIND_LABEL[d.kind]}{d.creditor ? ' · ' + d.creditor : ''}</div>
              </div>
              <button class="cat-edit static" on:click={() => (debtModal = { debt: d })} aria-label="Редактировать"><Pencil size={13} /></button>
            </div>

            <div class="debt-bar-row">
              <div class="bar-track"><div class="bar" style="width:{d.progress}%;background:{d.color}"></div></div>
              <span class="faint" style="font-size:12px">{d.progress}%</span>
            </div>

            <div class="between debt-nums">
              <div>
                <div class="faint" style="font-size:11px">Осталось</div>
                <div class="mono" style="font-weight:800;font-size:17px">{fmtAmount(d.remaining, d.currency)}</div>
              </div>
              <div style="text-align:right">
                <div class="faint" style="font-size:11px">из {fmtAmount(d.total_amount, d.currency)}</div>
                {#if d.monthly_payment > 0}<div class="faint" style="font-size:11px">взнос {fmtAmount(d.monthly_payment, d.currency)}</div>{/if}
                {#if d.pay_day}<div class="faint" style="font-size:11px">{payDayHint(d.pay_day)}</div>{/if}
              </div>
            </div>

            {#if d.remaining <= 0}
              <button class="btn pay-btn" on:click={() => setArchived(d, true)}>
                <Archive size={16} /> Выплачен — в архив
              </button>
            {:else}
              <button class="btn btn-primary pay-btn" on:click={() => (payModal = { debt: d })}>
                <HandCoins size={16} /> Внести платёж
              </button>
            {/if}
          </div>
        {/each}
      </div>
    {/if}

    {#if showArchive}
      <div class="card list" style="margin-top:12px">
        {#each archivedDebts as d (d.id)}
          <div class="tx">
            <div class="icon-badge sm" style="background:{d.color}"><Icon name={d.icon} size={16} /></div>
            <div class="grow tx-info">
              <div class="tx-title">{d.name}</div>
              <div class="faint tx-sub">
                {KIND_LABEL[d.kind]} · выплачено {fmtAmount(d.paid, d.currency)} из {fmtAmount(d.total_amount, d.currency)}
              </div>
            </div>
            <button class="btn btn-ghost" on:click={() => setArchived(d, false)}>Вернуть</button>
          </div>
        {/each}
        {#if archivedDebts.length === 0}<div class="empty pad">Архив пуст</div>{/if}
      </div>
    {/if}
  </section>

  <!-- Категории трат -->
  <section>
    <div class="sec-head">
      <h3>Категории трат</h3>
      <div class="row" style="gap:10px">
        <span class="faint" style="font-size:12px">за {monthLabel}</span>
        <button class="btn btn-ghost btn-icon" on:click={() => (catModal = {})}><Plus size={18} /></button>
      </div>
    </div>
    <div class="cat-grid">
      {#each categories as c (c.id)}
        <div class="cat-card card">
          <button class="cat-main" on:click={() => (opModal = { initial: { type: 'expense', category_id: c.id } })}>
            <div class="cat-head">
              <div class="icon-badge" style="background:{c.color}"><Icon name={c.icon} size={20} /></div>
              {#if catPct[c.id]}<span class="cat-pct">{catPct[c.id]}%</span>{/if}
            </div>
            <div class="cat-name">{c.name}</div>
            <div class="cat-spent mono">{fmtAmount(catSpent[c.id] || 0, reportCurrency).replace('+', '')}</div>
            {#if c.monthly_limit > 0}
              {@const lim = convertAmount(c.monthly_limit, c.limit_currency || 'BYN', reportCurrency, rate)}
              {#if lim}
                {@const over = (catSpent[c.id] || 0) > lim}
                <div class="cat-bar"><div style="width:{Math.min(100, ((catSpent[c.id] || 0) / lim) * 100)}%;background:{over ? 'var(--neg)' : c.color}"></div></div>
                <div class="faint" style="font-size:11px">из {fmtAmount(lim, reportCurrency)}</div>
              {/if}
            {/if}
            {#if c.description}<div class="cat-desc faint">{c.description}</div>{/if}
          </button>
          <div class="cat-foot">
            <button class="cat-fbtn" on:click|stopPropagation={() => (catHistory = { category: c })} aria-label="История операций">
              <History size={14} /> <span>История</span>
            </button>
            <button class="cat-fbtn icon" on:click|stopPropagation={() => (catModal = { category: c })} aria-label="Редактировать">
              <Pencil size={14} />
            </button>
          </div>
        </div>
      {/each}
      <button class="cat-card card add" on:click={() => (catModal = {})}>
        <div class="icon-badge ghost"><Plus size={20} /></div>
        <div class="cat-name dim">Добавить</div>
      </button>
    </div>
  </section>

  <!-- Последние операции -->
  <section>
    <div class="sec-head"><h3>Операции за {monthLabel}</h3></div>
    <input class="search" placeholder="Поиск: заметка, счёт, категория" bind:value={q} on:input={() => (page = 0)} />
    <div class="card list">
      {#each pageTxs as t (t.id)}
        <button class="tx" on:click={() => handleTxClick(t)}>
          <div class="icon-badge sm" style="background:{(t.type === 'expense' && t.category_color) || (t.type === 'debt_payment' && t.debt_color) || t.account_color || 'var(--accent)'}">
            <svelte:component this={txMeta[t.type].icon} size={16} color="#fff" />
          </div>
          <div class="grow tx-info">
            <div class="tx-title">
              {#if t.type === 'income'}Доход · {t.account_name}
              {:else if t.type === 'expense'}{t.category_name || 'Без категории'}
              {:else if t.type === 'debt_payment'}Платёж · {t.debt_name || 'долг'}
              {:else}{t.account_name} → {t.dest_account_name}{/if}
            </div>
            <div class="faint tx-sub">{fmtDate(t.occurred_at)}{t.note ? ' · ' + t.note : ''}</div>
          </div>
          <div class="mono tx-amt {txMeta[t.type].cls}">
            {txMeta[t.type].sign}{fmtAmount(t.amount, t.currency).replace('+', '')}
          </div>
        </button>
      {/each}
      {#if visibleTxs.length === 0}<div class="empty pad">{q.trim() ? 'Ничего не найдено' : 'Нет операций за этот месяц.'}</div>{/if}
    </div>
    {#if pageCount > 1}
      <div class="pager">
        <button class="btn btn-ghost btn-icon" on:click={() => (page -= 1)} disabled={page === 0} aria-label="Назад"><ChevronLeft size={18} /></button>
        <span class="faint" style="font-size:13px">{page + 1} из {pageCount} · всего {visibleTxs.length}</span>
        <button class="btn btn-ghost btn-icon" on:click={() => (page += 1)} disabled={page >= pageCount - 1} aria-label="Вперёд"><ChevronRight size={18} /></button>
      </div>
    {/if}
  </section>

  <!-- FAB -->
  <button class="fab" on:click={() => (opModal = { initial: {} })} aria-label="Добавить операцию">
    <Plus size={26} color="#fff" />
  </button>
{/if}

{#if opModal}
  <OperationModal {accounts} {categories} {rate} initial={opModal.initial || {}} tx={opModal.tx || null}
    on:close={() => (opModal = null)} on:saved={onSaved} />
{/if}
{#if accModal}
  <AccountModal account={accModal.account || null} {users}
    on:close={() => (accModal = null)} on:saved={onSaved} />
{/if}
{#if catModal}
  <CategoryModal category={catModal.category || null}
    on:close={() => (catModal = null)} on:saved={onSaved} />
{/if}
{#if debtModal}
  <DebtModal debt={debtModal.debt || null} {rate}
    on:close={() => (debtModal = null)} on:saved={onSaved} />
{/if}
{#if payModal}
  <DebtPaymentModal debt={payModal.debt} {accounts} {rate}
    on:close={() => (payModal = null)} on:saved={onSaved} />
{/if}
{#if catHistory}
  <CategoryHistoryModal category={catHistory.category} dateFrom={monthFrom} dateTo={monthTo} {monthLabel}
    on:close={() => (catHistory = null)}
    on:changed={load}
    on:edit={(e) => { catHistory = null; opModal = { tx: e.detail } }} />
{/if}

<style>
  .center { display: grid; place-items: center; height: 60vh; color: var(--accent); }
  .hero { padding: 20px; display: flex; flex-direction: column; gap: 18px; margin-bottom: 22px; }
  .rate {
    display: inline-flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 600;
    background: var(--surface-strong); border: 1px solid var(--border); color: var(--text-dim);
    padding: 7px 12px; border-radius: 999px; transition: color var(--transition);
  }
  .rate:hover { color: var(--text); }
  .total-val { font-size: 34px; font-weight: 800; letter-spacing: -1px; margin-top: 2px; }

  .month-nav {
    display: flex; align-items: center; justify-content: space-between; gap: 10px;
    background: var(--surface-strong); border: 1px solid var(--border);
    border-radius: 999px; padding: 4px 6px;
  }
  .mnav-btn {
    width: 34px; height: 34px; border-radius: 50%; display: grid; place-items: center;
    background: none; border: none; color: var(--text-dim); transition: color var(--transition), background var(--transition);
  }
  .mnav-btn:hover { color: var(--text); background: var(--surface); }
  .mnav-label { font-size: 15px; font-weight: 700; display: inline-flex; align-items: center; gap: 8px; }
  .mnav-tag {
    font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em;
    color: var(--accent); background: var(--accent-glow); padding: 2px 8px; border-radius: 999px;
  }

  .flows { display: flex; align-items: center; gap: 14px; margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--border); }
  .flow-item { display: flex; flex-direction: column; gap: 2px; }
  .flow-item .faint { font-size: 11px; }
  .flow-item .mono { font-size: 15px; font-weight: 700; }

  .networth { display: flex; align-items: center; gap: 14px; margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--border); }
  .nw-item { display: flex; flex-direction: column; gap: 2px; }
  .nw-item .faint { font-size: 11px; }
  .nw-item .mono { font-size: 15px; font-weight: 700; }
  .nw-sep { width: 1px; align-self: stretch; background: var(--border); }

  section { margin-bottom: 24px; }
  .sec-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; padding: 0 2px; }
  .sec-head h3 { font-size: 15px; font-weight: 700; }

  .grid2 { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
  @media (min-width: 560px) { .grid2 { grid-template-columns: repeat(3, 1fr); } }
  @media (min-width: 760px) { .grid2 { grid-template-columns: repeat(4, 1fr); } }

  .empty { color: var(--text-faint); font-size: 14px; padding: 6px 2px; grid-column: 1 / -1; }
  .empty.pad { padding: 22px; text-align: center; }

  .cat-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 12px; }
  .cat-card { position: relative; padding: 14px; }
  .cat-main { width: 100%; background: none; border: none; text-align: left; display: flex; flex-direction: column; gap: 7px; color: inherit; }
  .cat-head { display: flex; align-items: center; justify-content: space-between; gap: 6px; }
  .cat-pct {
    font-size: 11px; font-weight: 700; color: var(--accent);
    background: var(--accent-glow); padding: 2px 7px; border-radius: 999px; white-space: nowrap;
  }
  .cat-name { font-size: 14px; font-weight: 600; }
  .cat-spent { font-size: 15px; font-weight: 800; letter-spacing: -0.3px; }
  .cat-desc { font-size: 11px; line-height: 1.3; }
  .cat-edit {
    width: 26px; height: 26px; border-radius: 8px;
    display: grid; place-items: center; background: var(--surface); border: 1px solid var(--border);
    color: var(--text-faint); transition: color var(--transition);
  }
  .cat-edit:hover { color: var(--text); }

  .cat-foot { display: flex; gap: 6px; margin-top: 12px; padding-top: 10px; border-top: 1px solid var(--border); }
  .cat-fbtn {
    flex: 1; display: inline-flex; align-items: center; justify-content: center; gap: 5px;
    height: 34px; border-radius: 10px; background: var(--surface); border: 1px solid var(--border);
    color: var(--text-dim); font-size: 11px; font-weight: 600;
    transition: color var(--transition), border-color var(--transition), background var(--transition);
  }
  .cat-fbtn.icon { flex: 0 0 auto; width: 40px; }
  .cat-fbtn:hover, .cat-fbtn:active { color: var(--text); border-color: var(--border-strong); }

  .debts { display: grid; grid-template-columns: 1fr; gap: 12px; }
  @media (min-width: 620px) { .debts { grid-template-columns: repeat(2, 1fr); } }
  .debt { padding: 16px; display: flex; flex-direction: column; gap: 13px; }
  .debt-top { display: flex; align-items: center; gap: 12px; }
  .debt-name { font-weight: 700; font-size: 15px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .debt-sub { font-size: 12px; }
  .debt-bar-row { display: flex; align-items: center; gap: 10px; }
  .debt-bar-row .bar-track { flex: 1; height: 8px; background: var(--surface-strong); border-radius: 999px; overflow: hidden; }
  .debt-bar-row .bar { height: 100%; border-radius: 999px; transition: width 0.5s cubic-bezier(0.4,0,0.2,1); }
  .debt-nums { align-items: flex-end; }
  .pay-btn { width: 100%; }

  .sv { text-align: left; width: 100%; cursor: pointer; transition: transform var(--transition), border-color var(--transition); }
  .sv:hover { transform: translateY(-2px); border-color: var(--border-strong); }
  .sv:hover .cat-edit.static { color: var(--text); }
  .cat-card.add { display: flex; flex-direction: column; gap: 9px; align-items: flex-start; border-style: dashed; }
  .icon-badge.ghost { background: var(--surface-strong); color: var(--text-dim); }
  .icon-badge.sm { width: 38px; height: 38px; border-radius: 11px; }

  .list { display: flex; flex-direction: column; padding: 6px; }
  .tx {
    display: flex; align-items: center; gap: 12px; padding: 10px; border-radius: 14px;
    background: none; border: none; color: inherit; text-align: left; transition: background var(--transition);
  }
  .tx:hover { background: var(--surface); }
  .tx-info { min-width: 0; }
  .tx-title { font-size: 14px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .tx-sub { font-size: 12px; }
  .tx-amt { font-size: 15px; font-weight: 700; white-space: nowrap; }
  .search { width: 100%; margin-bottom: 10px; }
  .pager { display: flex; align-items: center; justify-content: center; gap: 14px; margin-top: 12px; }
  .arch-toggle {
    display: inline-flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 600;
    background: var(--surface-strong); border: 1px solid var(--border); color: var(--text-dim);
    padding: 6px 11px; border-radius: 999px; transition: color var(--transition);
  }
  .arch-toggle:hover { color: var(--text); }
  .cat-bar { height: 6px; background: var(--surface-strong); border-radius: 999px; overflow: hidden; }
  .cat-bar > div { height: 100%; border-radius: 999px; }

  .fab {
    position: fixed; right: 18px; bottom: 104px; z-index: 45;
    width: 58px; height: 58px; border-radius: 50%; border: none;
    background: var(--grad); box-shadow: 0 14px 30px -8px var(--accent-glow);
    display: grid; place-items: center; transition: transform var(--transition);
  }
  .fab:hover { transform: scale(1.06) translateY(-2px); }
  .fab:active { transform: scale(0.97); }
</style>
