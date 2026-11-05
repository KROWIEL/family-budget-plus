<script>
  import { createEventDispatcher, onMount } from 'svelte'
  import { Loader2, Trash2, TrendingDown } from 'lucide-svelte'
  import Modal from './Modal.svelte'
  import Icon from './Icon.svelte'
  import { api } from '../lib/api.js'
  import { toast } from '../lib/stores.js'
  import { fmtAmount, fmtDate } from '../lib/format.js'

  export let category
  export let dateFrom
  export let dateTo
  export let monthLabel = ''

  const dispatch = createEventDispatcher()

  let list = []
  let loading = true
  let deletingId = null

  async function load() {
    loading = true
    try {
      list = await api.get(
        `/transactions?type=expense&category_id=${category.id}&date_from=${dateFrom}&date_to=${dateTo}&limit=500`
      )
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      loading = false
    }
  }

  async function remove(t) {
    if (!confirm('Удалить эту операцию?')) return
    deletingId = t.id
    try {
      await api.del(`/transactions/${t.id}`)
      list = list.filter((x) => x.id !== t.id)
      toast('Операция удалена', 'success')
      dispatch('changed')
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      deletingId = null
    }
  }

  onMount(load)
</script>

<Modal title="История · {category.name}" on:close>
  <div class="sub faint">{monthLabel}{list.length ? ` · ${list.length} оп.` : ''}</div>

  {#if loading}
    <div class="center"><Loader2 size={24} class="spin" /></div>
  {:else if list.length === 0}
    <div class="empty">Нет операций в этой категории за выбранный месяц.</div>
  {:else}
    <div class="list">
      {#each list as t (t.id)}
        <div class="row">
          <button class="tx" on:click={() => dispatch('edit', t)}>
            <div class="icon-badge sm" style="background:{category.color}">
              <TrendingDown size={15} color="#fff" />
            </div>
            <div class="grow info">
              <div class="title">{t.note || category.name}</div>
              <div class="faint sub2">{fmtDate(t.occurred_at)} · {t.account_name}{t.created_by_name ? ' · ' + t.created_by_name : ''}</div>
            </div>
            <div class="mono amt neg">−{fmtAmount(t.amount, t.currency).replace('+', '')}</div>
          </button>
          <button class="del" on:click={() => remove(t)} disabled={deletingId === t.id} aria-label="Удалить">
            {#if deletingId === t.id}<Loader2 size={14} class="spin" />{:else}<Trash2 size={14} />{/if}
          </button>
        </div>
      {/each}
    </div>
  {/if}
</Modal>

<style>
  .sub { font-size: 13px; margin: -8px 0 14px; }
  .center { display: grid; place-items: center; padding: 30px; color: var(--accent); }
  .empty { color: var(--text-faint); font-size: 14px; text-align: center; padding: 24px 8px; }
  .list { display: flex; flex-direction: column; gap: 4px; max-height: 60vh; overflow-y: auto; margin: 0 -6px; padding: 0 6px; }
  .row { display: flex; align-items: center; gap: 6px; }
  .tx {
    flex: 1; min-width: 0; display: flex; align-items: center; gap: 12px; padding: 10px;
    border-radius: 12px; background: none; border: none; color: inherit; text-align: left;
    transition: background var(--transition);
  }
  .tx:hover { background: var(--surface); }
  .info { min-width: 0; }
  .title { font-size: 14px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .sub2 { font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .amt { font-size: 14px; font-weight: 700; white-space: nowrap; }
  .del {
    width: 34px; height: 34px; flex-shrink: 0; border-radius: 10px; display: grid; place-items: center;
    background: var(--surface); border: 1px solid var(--border); color: var(--text-faint);
    transition: color var(--transition), border-color var(--transition);
  }
  .del:hover { color: var(--neg); border-color: var(--neg); }
</style>
