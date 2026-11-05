<script>
  import { createEventDispatcher } from 'svelte'
  import { Loader2, Trash2 } from 'lucide-svelte'
  import Modal from './Modal.svelte'
  import IconPicker from './IconPicker.svelte'
  import ColorPicker from './ColorPicker.svelte'
  import { CATEGORY_ICONS } from '../lib/icons.js'
  import { api } from '../lib/api.js'
  import { toast } from '../lib/stores.js'
  import { parseAmount } from '../lib/format.js'

  export let category = null
  const dispatch = createEventDispatcher()
  const isEdit = !!category

  let name = category?.name || ''
  let description = category?.description || ''
  let icon = category?.icon || 'shopping-cart'
  let color = category?.color || '#6366f1'
  let monthly_limit = category?.monthly_limit || ''
  let limit_currency = category?.limit_currency || 'BYN'
  let busy = false

  async function save() {
    if (!name.trim() || busy) return
    busy = true
    const limit = parseAmount(monthly_limit)
    const body = {
      name, description, icon, color,
      monthly_limit: Number.isFinite(limit) && limit > 0 ? limit : 0,   // пустое поле = без лимита
      limit_currency
    }
    try {
      if (isEdit) await api.patch(`/categories/${category.id}`, body)
      else await api.post('/categories', body)
      toast('Категория сохранена', 'success')
      dispatch('saved')
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      busy = false
    }
  }

  async function remove() {
    if (!confirm('Удалить категорию? Если по ней есть траты — она уйдёт в архив.')) return
    busy = true
    try {
      await api.del(`/categories/${category.id}`)
      toast('Категория удалена', 'success')
      dispatch('saved')
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      busy = false
    }
  }
</script>

<Modal title={isEdit ? 'Редактировать категорию' : 'Новая категория'} on:close>
  <div class="form">
    <div class="field">
      <label for="cn">Название</label>
      <input id="cn" bind:value={name} placeholder="Например, Продукты" />
    </div>
    <div class="field">
      <label for="cd">Краткое описание</label>
      <input id="cd" bind:value={description} placeholder="Необязательно" />
    </div>
    <div class="field">
      <label for="cl">Лимит на месяц</label>
      <div class="amount-wrap">
        <input id="cl" type="text" inputmode="decimal" bind:value={monthly_limit} placeholder="Без лимита" />
        <div class="cur-toggle">
          <button type="button" class:active={limit_currency === 'BYN'} on:click={() => (limit_currency = 'BYN')}>Br</button>
          <button type="button" class:active={limit_currency === 'USD'} on:click={() => (limit_currency = 'USD')}>$</button>
        </div>
      </div>
    </div>
    <div class="field">
      <span class="lbl">Иконка</span>
      <IconPicker bind:value={icon} options={CATEGORY_ICONS} />
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
  .actions { display: flex; gap: 10px; margin-top: 6px; }
  .amount-wrap { position: relative; }
  .amount-wrap input { padding-right: 96px; }
  .cur-toggle {
    position: absolute; right: 8px; top: 50%; transform: translateY(-50%);
    display: flex; gap: 2px; background: var(--surface); border: 1px solid var(--border);
    border-radius: 999px; padding: 3px;
  }
  .cur-toggle button {
    border: none; background: transparent; color: var(--text-dim);
    padding: 4px 10px; border-radius: 999px; font-weight: 700; font-size: 13px;
  }
  .cur-toggle button.active { background: var(--grad); color: #fff; }
</style>
