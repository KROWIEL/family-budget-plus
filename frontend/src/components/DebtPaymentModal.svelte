<script>
  import { createEventDispatcher } from 'svelte'
  import { Loader2, ArrowRight } from 'lucide-svelte'
  import Modal from './Modal.svelte'
  import { api } from '../lib/api.js'
  import { toast } from '../lib/stores.js'
  import { fmtAmount, currencySymbol, todayISO, parseAmount, convertAmount } from '../lib/format.js'

  export let debt
  export let accounts = []
  export let rate = null

  const dispatch = createEventDispatcher()
  // платить логично с реальных счетов (карта/наличные), но разрешим любой
  $: payAccounts = accounts.filter((a) => a.kind !== 'income')

  let account_id = null
  let amount = ''
  let amountCur = debt.currency
  let occurred_at = todayISO()
  let note = ''
  let busy = false
  $: if (account_id === null && payAccounts.length) account_id = payAccounts[0].id
  $: srcAcc = accounts.find((a) => a.id === account_id)
  $: srcCur = srcAcc?.currency || debt.currency

  const round2 = (n) => Math.round(n * 100) / 100

  $: typed = (() => {
    const a = parseAmount(amount)
    return a && a > 0 ? round2(a) : 0
  })()

  // Вторая сторона конвертации: ввели в валюте счёта — правим погашение долга,
  // иначе — списание со счёта. Подставляется по НБРБ, банк может посчитать иначе.
  $: otherIsDebt = amountCur === srcCur
  $: otherCur = otherIsDebt ? debt.currency : srcCur
  $: autoOther = typed ? convertAmount(typed, amountCur, otherCur, rate) : 0

  let otherEdit = ''
  let otherDirty = false
  let otherKey = ''
  $: {
    const key = `${amount}|${amountCur}|${account_id}`
    if (key !== otherKey) { otherKey = key; otherDirty = false }
    if (!otherDirty) otherEdit = autoOther ? String(autoOther) : ''
  }

  async function save() {
    if (!typed) { toast('Укажите сумму', 'error'); return }
    if (!account_id) { toast('Выберите счёт', 'error'); return }
    let cardAmount = typed
    let applied = null
    if (otherCur !== amountCur) {
      const other = round2(parseAmount(otherEdit) || 0)
      if (other <= 0) {
        toast(otherIsDebt ? 'Укажите сумму погашения долга' : 'Укажите сумму списания со счёта', 'error')
        return
      }
      if (otherIsDebt) {
        if (autoOther == null || Math.abs(other - autoOther) >= 0.005) applied = other
      } else {
        cardAmount = other
        if (srcCur !== debt.currency) applied = typed
      }
    }
    busy = true
    const body = {
      type: 'debt_payment',
      amount: cardAmount,
      account_id,
      debt_id: debt.id,
      note,
      occurred_at
    }
    if (applied != null) body.applied_amount = applied
    try {
      await api.post('/transactions', body)
      toast('Платёж внесён', 'success')
      dispatch('saved')
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      busy = false
    }
  }
</script>

<Modal title={`Платёж · ${debt.name}`} on:close>
  <div class="form">
    <div class="remain">
      <span class="dim" style="font-size:13px">Остаток к выплате</span>
      <div class="mono val">{fmtAmount(debt.remaining, debt.currency)}</div>
    </div>

    <div class="field">
      <label for="pa">Списать со счёта</label>
      <select id="pa" bind:value={account_id}>
        {#each payAccounts as a}<option value={a.id}>{a.name} · {currencySymbol(a.currency)}</option>{/each}
      </select>
    </div>

    <div class="field">
      <label for="pamt">Сумма платежа</label>
      <div class="amount-wrap">
        <input id="pamt" type="text" inputmode="decimal" bind:value={amount} placeholder="0.00" />
        <div class="cur-toggle">
          <button type="button" class:active={amountCur === 'BYN'} on:click={() => (amountCur = 'BYN')}>Br</button>
          <button type="button" class:active={amountCur === 'USD'} on:click={() => (amountCur = 'USD')}>$</button>
        </div>
      </div>
    </div>

    {#if otherCur !== amountCur}
      <div class="field">
        <label for="pother">
          {otherIsDebt ? 'Уйдёт в погашение долга' : 'Спишется со счёта'} ({currencySymbol(otherCur)}) — можно поправить
        </label>
        <input id="pother" type="text" inputmode="decimal" bind:value={otherEdit}
          on:input={() => (otherDirty = true)} placeholder="0.00" />
        {#if autoOther}
          <div class="convert">
            <span>{fmtAmount(typed, amountCur)}</span>
            <ArrowRight size={16} />
            <span class="pos">{fmtAmount(autoOther, otherCur)}</span>
            <span class="badge" style="margin-left:auto">НБРБ {rate}</span>
          </div>
          <div class="hint">Если банк посчитал по другому курсу, впишите фактическую сумму.</div>
        {:else if autoOther === null}
          <div class="convert neg">Курс НБРБ недоступен — впишите сумму вручную</div>
        {/if}
      </div>
    {/if}

    <div class="field">
      <label for="pd">Дата</label>
      <input id="pd" type="date" bind:value={occurred_at} />
    </div>
    <div class="field">
      <label for="pn">Заметка</label>
      <input id="pn" bind:value={note} placeholder="Необязательно" />
    </div>

    <button class="btn btn-primary" on:click={save} disabled={busy}>
      {#if busy}<Loader2 size={17} class="spin" />{/if} Внести платёж
    </button>
  </div>
</Modal>

<style>
  .form { display: flex; flex-direction: column; gap: 15px; }
  .remain { background: var(--surface); border: 1px solid var(--border); border-radius: 14px; padding: 12px 16px; display: flex; flex-direction: column; gap: 3px; }
  .remain .val { font-size: 22px; font-weight: 800; }
  .amount-wrap { position: relative; }
  .amount-wrap input { font-size: 24px; font-weight: 700; padding-right: 96px; }
  .cur-toggle {
    position: absolute; right: 8px; top: 50%; transform: translateY(-50%);
    display: flex; gap: 2px; background: var(--surface); border: 1px solid var(--border);
    border-radius: 999px; padding: 3px;
  }
  .cur-toggle button {
    border: none; background: transparent; color: var(--text-dim);
    padding: 5px 11px; border-radius: 999px; font-weight: 700; font-size: 13px;
    transition: background var(--transition), color var(--transition);
  }
  .cur-toggle button.active { background: var(--grad); color: #fff; }
  .hint { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--text-dim); background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 9px 13px; margin-top: 8px; }
  .convert { display: flex; align-items: center; gap: 10px; font-weight: 600; font-size: 14px; background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 10px 14px; }
  .convert.neg { color: var(--neg); }
  .field .convert { margin-top: 8px; }
</style>
