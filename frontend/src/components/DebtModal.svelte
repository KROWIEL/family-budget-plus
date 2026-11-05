<script>
  import { createEventDispatcher } from 'svelte'
  import { Loader2, Trash2 } from 'lucide-svelte'
  import Modal from './Modal.svelte'
  import IconPicker from './IconPicker.svelte'
  import ColorPicker from './ColorPicker.svelte'
  import { DEBT_ICONS } from '../lib/icons.js'
  import { currencySymbol, parseAmount } from '../lib/format.js'
  import { api } from '../lib/api.js'
  import { toast } from '../lib/stores.js'

  export let debt = null
  export let rate = null
  const dispatch = createEventDispatcher()
  const isEdit = !!debt

  const KINDS = [
    { id: 'debt', label: 'Долг' },
    { id: 'credit', label: 'Кредит' },
    { id: 'leasing', label: 'Лизинг' }
  ]

  let name = debt?.name || ''
  let kind = debt?.kind || 'credit'
  let creditor = debt?.creditor || ''
  let currency = debt?.currency || 'BYN'
  let total_amount = debt?.total_amount ?? ''
  let remaining_start = debt?.remaining_start ?? ''
  let monthly_payment = debt?.monthly_payment ?? ''
  let pay_day = debt?.pay_day || 0
  let icon = debt?.icon || 'landmark'
  let color = debt?.color || '#f43f5e'
  let note = debt?.note || ''
  let busy = false

  // при создании: если остаток пуст — подставляем полную сумму
  $: if (!isEdit && total_amount !== '' && remaining_start === '') remaining_start = total_amount

  const round2 = (n) => Math.round(n * 100) / 100

  // смена валюты долга: пересчитываем введённые суммы по текущему курсу НБРБ
  function switchCurrency(nc) {
    if (nc === currency) return
    if (rate) {
      const f = nc === 'USD' ? 1 / rate : rate
      if (total_amount !== '' && total_amount != null) total_amount = round2(parseAmount(total_amount) * f)
      if (remaining_start !== '' && remaining_start != null) remaining_start = round2(parseAmount(remaining_start) * f)
      if (monthly_payment !== '' && monthly_payment != null && parseAmount(monthly_payment) > 0)
        monthly_payment = round2(parseAmount(monthly_payment) * f)
    } else if (nc !== currency) {
      toast('Курс НБРБ недоступен — суммы не пересчитаны', 'error')
    }
    currency = nc
  }

  async function save() {
    if (!name.trim() || busy) return
    busy = true
    const body = {
      name, kind, creditor, currency,
      total_amount: parseAmount(total_amount) || 0,
      remaining_start: parseAmount(remaining_start) || 0,
      monthly_payment: parseAmount(monthly_payment) || 0,
      pay_day: Math.min(31, Math.max(0, parseInt(pay_day, 10) || 0)),
      icon, color, note
    }
    try {
      if (isEdit) await api.patch(`/debts/${debt.id}`, body)
      else await api.post('/debts', body)
      toast('Обязательство сохранено', 'success')
      dispatch('saved')
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      busy = false
    }
  }

  async function remove() {
    if (!confirm('Удалить? Если есть платежи — уйдёт в архив.')) return
    busy = true
    try {
      await api.del(`/debts/${debt.id}`)
      toast('Удалено', 'success')
      dispatch('saved')
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      busy = false
    }
  }
</script>

<Modal title={isEdit ? 'Редактировать обязательство' : 'Новый долг / кредит'} on:close>
  <div class="form">
    <div class="field">
      <span class="lbl">Тип</span>
      <div class="segmented">
        {#each KINDS as k}
          <button type="button" class:active={kind === k.id} on:click={() => (kind = k.id)}>{k.label}</button>
        {/each}
      </div>
    </div>

    <div class="field">
      <label for="dn">Название</label>
      <input id="dn" bind:value={name} placeholder="Напр. Кредит на авто" />
    </div>

    <div class="field">
      <label for="dc">Кредитор (кому/куда платить)</label>
      <input id="dc" bind:value={creditor} placeholder="Напр. Беларусбанк" />
    </div>

    <div class="field">
      <span class="lbl">Валюта</span>
      <div class="segmented">
        <button type="button" class:active={currency === 'BYN'} on:click={() => switchCurrency('BYN')}>Br · BYN</button>
        <button type="button" class:active={currency === 'USD'} on:click={() => switchCurrency('USD')}>$ · USD</button>
      </div>
    </div>

    <div class="two">
      <div class="field grow">
        <label for="dt">Полная сумма ({currencySymbol(currency)})</label>
        <input id="dt" type="text" inputmode="decimal" bind:value={total_amount} placeholder="0.00" />
      </div>
      <div class="field grow">
        <label for="dr">Остаток ({currencySymbol(currency)})</label>
        <input id="dr" type="text" inputmode="decimal" bind:value={remaining_start} placeholder="0.00" />
      </div>
    </div>

    <div class="field">
      <label for="dm">Ежемесячный платёж ({currencySymbol(currency)}, необязательно)</label>
      <input id="dm" type="text" inputmode="decimal" bind:value={monthly_payment} placeholder="0.00" />
    </div>
    <div class="field">
      <label for="dd">День платежа (0 — без напоминания)</label>
      <input id="dd" type="text" inputmode="numeric" bind:value={pay_day} placeholder="0" />
    </div>

    <div class="field">
      <span class="lbl">Иконка</span>
      <IconPicker bind:value={icon} options={DEBT_ICONS} />
    </div>
    <div class="field">
      <span class="lbl">Цвет</span>
      <ColorPicker bind:value={color} />
    </div>
    <div class="field">
      <label for="dnote">Заметка</label>
      <input id="dnote" bind:value={note} placeholder="Необязательно" />
    </div>

    <div class="actions">
      {#if isEdit}
        <button class="btn btn-ghost" style="color:var(--neg)" on:click={remove} disabled={busy}>
          <Trash2 size={17} /> Удалить
        </button>
      {/if}
      <button class="btn btn-primary grow" on:click={save} disabled={busy || !name.trim()}>
        {#if busy}<Loader2 size={17} class="spin" />{/if} Сохранить
      </button>
    </div>
  </div>
</Modal>

<style>
  .form { display: flex; flex-direction: column; gap: 15px; }
  .segmented { width: 100%; }
  .segmented button { flex: 1; }
  .two { display: flex; gap: 12px; }
  .actions { display: flex; gap: 10px; margin-top: 6px; }
</style>
