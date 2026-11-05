<script>
  import { createEventDispatcher } from 'svelte'
  import { Loader2, Trash2, ArrowRight } from 'lucide-svelte'
  import Modal from './Modal.svelte'
  import { api } from '../lib/api.js'
  import { toast } from '../lib/stores.js'
  import { fmtAmount, currencySymbol, todayISO, parseAmount, convertAmount } from '../lib/format.js'

  export let accounts = []
  export let categories = []
  export let rate = null
  export let initial = {}
  export let tx = null

  const dispatch = createEventDispatcher()
  const isEdit = !!tx

  const TYPES = [
    { id: 'income', label: 'Доход' },
    { id: 'expense', label: 'Расход' },
    { id: 'transfer', label: 'Перевод' }
  ]

  const initAcc = accounts.find((a) => a.id === (tx?.account_id ?? initial.account_id ?? accounts[0]?.id))

  let type = tx?.type || initial.type || 'expense'
  let amount = tx?.amount ?? ''
  let account_id = tx?.account_id ?? initial.account_id ?? accounts[0]?.id ?? null
  let dest_account_id = tx?.dest_account_id ?? null
  let category_id = tx?.category_id ?? initial.category_id ?? null
  let note = tx?.note || ''
  let occurred_at = tx?.occurred_at || todayISO()
  // валюта, в которой пользователь ВВОДИТ сумму (можно вводить в Br даже с $-счёта)
  let amountCur = tx?.currency || initAcc?.currency || 'BYN'
  let busy = false

  $: srcAcc = accounts.find((a) => a.id === account_id)
  $: dstAcc = accounts.find((a) => a.id === dest_account_id)
  $: srcCur = srcAcc?.currency || 'BYN'

  // при смене счёта — по умолчанию вводим в валюте этого счёта
  let lastSrcCur = srcCur
  $: if (srcCur !== lastSrcCur) { amountCur = srcCur; lastSrcCur = srcCur }

  const round2 = (n) => Math.round(n * 100) / 100

  $: typed = (() => {
    const a = parseAmount(amount)
    return a && a > 0 ? round2(a) : 0
  })()

  // сумма в валюте счёта по курсу НБРБ; null — курса нет
  $: autoBase = typed ? convertAmount(typed, amountCur, srcCur, rate) : 0

  // сумма введена не в валюте счёта: списание/зачисление по НБРБ, но банк может посчитать иначе
  let srcEdit = ''
  let srcDirty = false
  let srcKey = `${amount}|${amountCur}|${account_id}`
  $: {
    const key = `${amount}|${amountCur}|${account_id}`
    if (key !== srcKey) { srcKey = key; srcDirty = false }
    if (!srcDirty) srcEdit = autoBase ? String(autoBase) : ''
  }

  // сумма, которая реально спишется/зачислится на счёт (в его валюте)
  $: baseAmount = (() => {
    if (amountCur === srcCur) return typed
    const v = parseAmount(srcEdit)
    return v && v > 0 ? round2(v) : 0
  })()

  // предпросмотр суммы зачисления для перевода (в валюте получателя)
  $: preview = (() => {
    if (type !== 'transfer' || !srcAcc || !dstAcc || !baseAmount) return null
    if (srcAcc.currency === dstAcc.currency) return { amount: baseAmount, converted: false, cur: dstAcc.currency }
    // ввели сумму сразу в валюте получателя — она и зачисляется
    const out = amountCur === dstAcc.currency ? typed : convertAmount(baseAmount, srcAcc.currency, dstAcc.currency, rate)
    return out == null ? null : { amount: out, converted: true, cur: dstAcc.currency }
  })()

  // сумма зачисления при переводе между валютами: по НБРБ, но банк может дать другую
  $: cross = type === 'transfer' && !!srcAcc && !!dstAcc && srcAcc.currency !== dstAcc.currency
  const editingCross = isEdit && tx.type === 'transfer' && tx.dest_amount != null && tx.dest_currency !== tx.currency
  let destEdit = editingCross ? String(tx.dest_amount) : ''
  let destDirty = editingCross
  let destKey = `${amount}|${amountCur}|${account_id}|${dest_account_id}`
  $: {
    const key = `${amount}|${amountCur}|${account_id}|${dest_account_id}`
    if (key !== destKey) { destKey = key; destDirty = false }
    if (!destDirty) destEdit = preview?.converted ? String(preview.amount) : ''
  }

  function accountLabel(a) {
    return `${a.name} · ${currencySymbol(a.currency)}`
  }

  async function save() {
    if (busy) return
    if (!parseAmount(amount) || parseAmount(amount) <= 0) { toast('Укажите сумму', 'error'); return }
    if (!account_id) { toast('Выберите счёт', 'error'); return }
    if (!baseAmount) {
      toast(type === 'income' ? 'Укажите сумму зачисления на счёт' : 'Укажите сумму списания со счёта', 'error')
      return
    }
    if (type === 'transfer' && (!dest_account_id || dest_account_id === account_id)) {
      toast('Выберите другой счёт назначения', 'error'); return
    }
    let destOverride = null
    if (cross && amountCur === dstAcc.currency) {
      destOverride = typed
    } else if (cross) {
      const d = parseAmount(destEdit)
      if (!d || d <= 0) { toast('Укажите сумму зачисления', 'error'); return }
      if (!preview?.converted || Math.abs(round2(d) - preview.amount) >= 0.005) destOverride = round2(d)
    }
    busy = true
    const body = {
      type,
      amount: baseAmount,
      account_id,
      dest_account_id: type === 'transfer' ? dest_account_id : null,
      category_id: type === 'expense' ? category_id : null,
      note,
      occurred_at
    }
    if (destOverride != null) body.applied_amount = destOverride
    try {
      if (isEdit) await api.patch(`/transactions/${tx.id}`, body)
      else await api.post('/transactions', body)
      toast('Операция сохранена', 'success')
      dispatch('saved')
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      busy = false
    }
  }

  async function remove() {
    if (!confirm('Удалить операцию?')) return
    busy = true
    try {
      await api.del(`/transactions/${tx.id}`)
      toast('Операция удалена', 'success')
      dispatch('saved')
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      busy = false
    }
  }
</script>

<Modal title={isEdit ? 'Операция' : 'Новая операция'} on:close>
  <div class="form">
    <div class="segmented types">
      {#each TYPES as t}
        <button type="button" class:active={type === t.id} on:click={() => (type = t.id)}>{t.label}</button>
      {/each}
    </div>

    <div class="field amount-field">
      <label for="amt">Сумма</label>
      <div class="amount-wrap">
        <input id="amt" type="text" inputmode="decimal" bind:value={amount} placeholder="0.00" />
        <div class="cur-toggle">
          <button type="button" class:active={amountCur === 'BYN'} on:click={() => (amountCur = 'BYN')}>Br</button>
          <button type="button" class:active={amountCur === 'USD'} on:click={() => (amountCur = 'USD')}>$</button>
        </div>
      </div>
    </div>

    <div class="field">
      <label for="acc">{type === 'income' ? 'Куда зачислить' : type === 'transfer' ? 'Со счёта' : 'Списать со счёта'}</label>
      <select id="acc" bind:value={account_id}>
        {#each accounts as a}<option value={a.id}>{accountLabel(a)}</option>{/each}
      </select>
    </div>

    {#if amountCur !== srcCur}
      <div class="field">
        <label for="srcamt">
          {type === 'income' ? 'Зачислится на счёт' : 'Спишется со счёта'} ({currencySymbol(srcCur)}) — можно поправить
        </label>
        <input id="srcamt" type="text" inputmode="decimal" bind:value={srcEdit}
          on:input={() => (srcDirty = true)} placeholder="0.00" />
        {#if autoBase}
          <div class="hint">
            <span>{fmtAmount(typed, amountCur)}</span>
            <ArrowRight size={14} />
            <span>{fmtAmount(autoBase, srcCur)}</span>
            <span class="badge" style="margin-left:auto">НБРБ {rate}</span>
          </div>
          <div class="sub">Если банк посчитал по другому курсу, впишите фактическую сумму.</div>
        {:else if autoBase === null}
          <div class="hint neg">Курс НБРБ недоступен — впишите сумму вручную</div>
        {/if}
      </div>
    {/if}

    {#if type === 'transfer'}
      <div class="field">
        <label for="dst">На счёт</label>
        <select id="dst" bind:value={dest_account_id}>
          <option value={null} disabled>Выберите счёт</option>
          {#each accounts.filter((a) => a.id !== account_id) as a}
            <option value={a.id}>{accountLabel(a)}</option>
          {/each}
        </select>
      </div>
      {#if cross && amountCur !== dstAcc.currency}
        <div class="field">
          <label for="dstamt">Зачислится на счёт ({currencySymbol(dstAcc.currency)}) — можно поправить</label>
          <input id="dstamt" type="text" inputmode="decimal" bind:value={destEdit}
            on:input={() => (destDirty = true)} placeholder="0.00" />
          {#if preview && preview.converted}
            <div class="hint">
              <span>{fmtAmount(baseAmount, srcCur)}</span>
              <ArrowRight size={14} />
              <span>{fmtAmount(preview.amount, preview.cur)}</span>
              <span class="badge" style="margin-left:auto">НБРБ {rate}</span>
            </div>
            <div class="sub">Если банк зачислил иначе, впишите фактическую сумму.</div>
          {:else}
            <div class="hint neg">Курс НБРБ недоступен — впишите сумму зачисления вручную</div>
          {/if}
        </div>
      {/if}
    {/if}

    {#if type === 'expense'}
      <div class="field">
        <span class="lbl">Категория</span>
        <div class="cat-grid">
          <button type="button" class="cat" class:sel={category_id === null} on:click={() => (category_id = null)}>
            Без категории
          </button>
          {#each categories as c}
            <button type="button" class="cat" class:sel={category_id === c.id}
              style={category_id === c.id ? `background:${c.color};border-color:${c.color};color:#fff` : ''}
              on:click={() => (category_id = c.id)}>
              {c.name}
            </button>
          {/each}
        </div>
      </div>
    {/if}

    <div class="two">
      <div class="field grow">
        <label for="dt">Дата</label>
        <input id="dt" type="date" bind:value={occurred_at} />
      </div>
    </div>

    <div class="field">
      <label for="nt">Заметка</label>
      <input id="nt" bind:value={note} placeholder="Необязательно" />
    </div>

    <div class="actions">
      {#if isEdit}
        <button class="btn btn-ghost" style="color:var(--neg)" on:click={remove} disabled={busy}>
          <Trash2 size={17} />
        </button>
      {/if}
      <button class="btn btn-primary grow" on:click={save} disabled={busy}>
        {#if busy}<Loader2 size={17} class="spin" />{/if} Сохранить
      </button>
    </div>
  </div>
</Modal>

<style>
  .form { display: flex; flex-direction: column; gap: 15px; }
  .types { width: 100%; }
  .types button { flex: 1; }
  .amount-wrap { position: relative; }
  .amount-wrap input { font-size: 26px; font-weight: 700; padding-right: 96px; text-align: left; }
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
  .hint {
    display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--text-dim);
    background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
    padding: 9px 13px; margin-top: 8px;
  }
  .hint.neg { color: var(--neg); }
  .sub { font-size: 12px; color: var(--text-dim); margin-top: 6px; }
  .cat-grid { display: flex; flex-wrap: wrap; gap: 8px; }
  .cat {
    padding: 8px 14px; border-radius: 999px; font-size: 13px; font-weight: 600;
    background: var(--surface); border: 1px solid var(--border); color: var(--text-dim);
    transition: all var(--transition);
  }
  .cat:hover { color: var(--text); }
  .cat.sel { color: #fff; }
  .two { display: flex; gap: 12px; }
  .actions { display: flex; gap: 10px; margin-top: 6px; }
</style>
