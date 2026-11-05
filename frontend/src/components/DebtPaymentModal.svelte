<script>
  import { createEventDispatcher } from 'svelte'
  import { Loader2, ArrowRight } from 'lucide-svelte'
  import Modal from './Modal.svelte'
  import { api } from '../lib/api.js'
  import { toast } from '../lib/stores.js'
  import { fmtAmount, currencySymbol, todayISO, parseAmount } from '../lib/format.js'

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
  let cardEdit = ''
  let cardDirty = false
  let cardKey = ''

  $: if (account_id === null && payAccounts.length) account_id = payAccounts[0].id
  $: srcAcc = accounts.find((a) => a.id === account_id)
  $: srcCur = srcAcc?.currency || debt.currency

  const round2 = (n) => Math.round(n * 100) / 100

  // сумма в валюте счёта (именно она спишется со счёта)
  $: baseAmount = (() => {
    const a = parseAmount(amount)
    if (!a || a <= 0) return 0
    if (amountCur === srcCur) return round2(a)
    if (!rate) return null
    if (amountCur === 'USD' && srcCur === 'BYN') return round2(a * rate)
    if (amountCur === 'BYN' && srcCur === 'USD') return round2(a / rate)
    return round2(a)
  })()

  // сколько уйдёт в погашение (в валюте долга) — не зависит от ручной правки списания
  $: applied = (() => {
    const typed = parseAmount(amount)
    if (!typed || typed <= 0) return null
    if (amountCur === debt.currency) return { amount: round2(typed), converted: amountCur !== srcCur }
    if (!srcAcc || !baseAmount) return null
    if (srcCur === debt.currency) return { amount: baseAmount, converted: false }
    if (!rate) return null
    const out = srcCur === 'USD' ? baseAmount * rate : baseAmount / rate
    return { amount: round2(out), converted: true }
  })()

  $: {
    const key = `${amount}|${amountCur}|${account_id}`
    if (key !== cardKey) { cardKey = key; cardDirty = false }
    if (!cardDirty) cardEdit = baseAmount ? String(baseAmount) : ''
  }

  async function save() {
    if (!parseAmount(amount) || parseAmount(amount) <= 0) { toast('Укажите сумму', 'error'); return }
    if (!account_id) { toast('Выберите счёт', 'error'); return }
    const cardAmount = amountCur === srcCur ? baseAmount : parseAmount(cardEdit)
    if (cardAmount == null || !cardAmount || cardAmount <= 0) {
      toast(baseAmount == null ? 'Курс НБРБ недоступен для пересчёта' : 'Укажите сумму списания', 'error')
      return
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
    if (srcCur !== debt.currency && amountCur === debt.currency) body.applied_amount = round2(parseAmount(amount))
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
      {#if amountCur !== srcCur}
        <div class="field" style="margin-top:8px">
          <label for="pcard">Спишется с карты ({currencySymbol(srcCur)}) — можно поправить</label>
          <input id="pcard" type="text" inputmode="decimal" bind:value={cardEdit} on:input={() => (cardDirty = true)} />
          <div class="hint">По курсу НБРБ {rate || '—'}. Если банк списал иначе, впишите фактическую сумму.</div>
        </div>
      {/if}
    </div>

    {#if applied && applied.converted && srcCur !== debt.currency}
      <div class="convert">
        <span>{fmtAmount(baseAmount, srcCur)}</span>
        <ArrowRight size={16} />
        <span class="pos">в погашение {fmtAmount(applied.amount, debt.currency)}</span>
        <span class="badge" style="margin-left:auto">курс {rate}</span>
      </div>
    {:else if srcAcc && srcCur !== debt.currency && !rate}
      <div class="convert neg">Курс НБРБ недоступен</div>
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
</style>
