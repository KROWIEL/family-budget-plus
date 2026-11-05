<script>
  import { createEventDispatcher } from 'svelte'
  import { Loader2, Trash2 } from 'lucide-svelte'
  import Modal from './Modal.svelte'
  import IconPicker from './IconPicker.svelte'
  import ColorPicker from './ColorPicker.svelte'
  import { ACCOUNT_ICONS } from '../lib/icons.js'
  import { api } from '../lib/api.js'
  import { toast } from '../lib/stores.js'
  import { parseAmount } from '../lib/format.js'

  export let account = null
  export let users = []

  const dispatch = createEventDispatcher()
  const isEdit = !!account

  const KINDS = [
    { id: 'income', label: 'Доход' },
    { id: 'card', label: 'Карта' },
    { id: 'cash', label: 'Наличные' },
    { id: 'savings', label: 'Копилка' }
  ]

  let name = account?.name || ''
  let kind = account?.kind || 'card'
  let owner_id = account?.owner_id ?? (users[0]?.id ?? null)
  let currency = account?.currency || 'BYN'
  let icon = account?.icon || 'wallet'
  let color = account?.color || '#6366f1'
  let hasGoal = (account?.goal_amount || 0) > 0
  let goal_amount = account?.goal_amount || 0
  let busy = false

  $: curSym = currency === 'USD' ? '$' : 'Br'

  async function save() {
    if (!name.trim() || busy) return
    busy = true
    const goal = kind === 'savings' && hasGoal ? parseAmount(goal_amount) || 0 : 0
    const body = { name, kind, owner_id: kind === 'savings' ? null : owner_id, currency, icon, color, goal_amount: goal }
    try {
      if (isEdit) await api.patch(`/accounts/${account.id}`, body)
      else await api.post('/accounts', body)
      toast('Счёт сохранён', 'success')
      dispatch('saved')
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      busy = false
    }
  }

  async function remove() {
    if (!confirm('Удалить счёт? Если по нему есть операции — он будет скрыт в архив.')) return
    busy = true
    try {
      await api.del(`/accounts/${account.id}`)
      toast('Счёт удалён', 'success')
      dispatch('saved')
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      busy = false
    }
  }
</script>

<Modal title={isEdit ? 'Редактировать счёт' : 'Новый счёт'} on:close>
  <div class="form">
    <div class="field">
      <label for="an">Название</label>
      <input id="an" bind:value={name} placeholder="Например, Карта — Иван" />
    </div>

    <div class="field">
      <span class="lbl">Тип</span>
      <div class="segmented wrap">
        {#each KINDS as k}
          <button type="button" class:active={kind === k.id} on:click={() => (kind = k.id)}>{k.label}</button>
        {/each}
      </div>
    </div>

    {#if kind !== 'savings'}
      <div class="field">
        <label for="ao">Владелец</label>
        <select id="ao" bind:value={owner_id}>
          {#each users as u}<option value={u.id}>{u.display_name}</option>{/each}
        </select>
      </div>
    {/if}

    <div class="field">
      <span class="lbl">Валюта</span>
      <div class="segmented">
        <button type="button" class:active={currency === 'BYN'} on:click={() => (currency = 'BYN')}>Br · BYN</button>
        <button type="button" class:active={currency === 'USD'} on:click={() => (currency = 'USD')}>$ · USD</button>
      </div>
      {#if isEdit && account && currency !== account.currency}
        <div class="hint">Баланс, операции{account.goal_amount > 0 ? ' и цель' : ''} будут пересчитаны в {currency} по текущему курсу НБРБ</div>
      {/if}
    </div>

    {#if kind === 'savings'}
      <div class="field">
        <label class="goal-toggle" for="agoal-on">
          <input id="agoal-on" type="checkbox" bind:checked={hasGoal} />
          <span class="lbl" style="margin:0">Цель по сумме (прогресс-бар)</span>
        </label>
        {#if hasGoal}
          <div class="amount-row">
            <input id="agoal" type="text" inputmode="decimal"
              bind:value={goal_amount} placeholder="Например, 5000" />
            <span class="cur-tag">{curSym}</span>
          </div>
          <div class="hint">Когда накопите эту сумму, копилка будет отмечена как достигнутая</div>
        {/if}
      </div>
    {/if}

    <div class="field">
      <span class="lbl">Иконка</span>
      <IconPicker bind:value={icon} options={ACCOUNT_ICONS} />
    </div>

    <div class="field">
      <span class="lbl">Цвет</span>
      <ColorPicker bind:value={color} />
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
  .segmented.wrap { flex-wrap: wrap; }
  .hint { font-size: 12px; color: var(--text-dim); background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 8px 12px; margin-top: 8px; }
  .actions { display: flex; gap: 10px; margin-top: 6px; }
  .goal-toggle { display: flex; align-items: center; gap: 10px; cursor: pointer; }
  .goal-toggle input { width: 18px; height: 18px; accent-color: var(--accent); }
  .amount-row { display: flex; align-items: center; gap: 8px; margin-top: 10px; }
  .amount-row input { flex: 1; }
  .cur-tag { font-weight: 700; color: var(--text-dim); min-width: 24px; text-align: center; }
</style>
