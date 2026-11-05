<script>
  import Icon from './Icon.svelte'
  import { fmtAmount } from '../lib/format.js'
  export let account
  export let reportCurrency = 'BYN'
</script>

<button class="acc card" on:click>
  <div class="top">
    <div class="icon-badge" style="background:{account.color}">
      <Icon name={account.icon} size={20} />
    </div>
    {#if account.currency !== reportCurrency && account.balance_report != null}
      <span class="badge">{fmtAmount(account.balance_report, reportCurrency)}</span>
    {/if}
  </div>
  <div class="name">{account.name}</div>
  <div class="bal mono" class:neg={account.balance < 0}>{fmtAmount(account.balance, account.currency)}</div>
</button>

<style>
  .acc {
    text-align: left; display: flex; flex-direction: column; gap: 10px;
    padding: 16px; cursor: pointer; transition: transform var(--transition), border-color var(--transition);
    border-radius: var(--radius-sm); width: 100%;
  }
  .acc:hover { transform: translateY(-2px); border-color: var(--border-strong); }
  .top { display: flex; align-items: center; justify-content: space-between; }
  .name { font-size: 13px; color: var(--text-dim); font-weight: 500; line-height: 1.2; }
  .bal { font-size: 19px; font-weight: 700; letter-spacing: -0.3px; }
</style>
