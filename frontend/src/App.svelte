<script>
  import { onMount } from 'svelte'
  import Router, { location, push } from 'svelte-spa-router'
  import { LayoutGrid, PieChart, User as UserIcon, Loader2 } from 'lucide-svelte'

  import { user, applyTheme } from './lib/stores.js'
  import { api } from './lib/api.js'
  import Login from './routes/Login.svelte'
  import Dashboard from './routes/Dashboard.svelte'
  import Stats from './routes/Stats.svelte'
  import Profile from './routes/Profile.svelte'
  import Avatar from './components/Avatar.svelte'
  import Toasts from './components/Toasts.svelte'

  let loading = true

  const routes = {
    '/': Dashboard,
    '/stats': Stats,
    '/profile': Profile,
    '*': Dashboard
  }

  const nav = [
    { path: '/', label: 'Бюджет', icon: LayoutGrid },
    { path: '/stats', label: 'Статистика', icon: PieChart },
    { path: '/profile', label: 'Профиль', icon: UserIcon }
  ]

  onMount(async () => {
    const stored = localStorage.getItem('bp_theme')
    applyTheme(stored || 'light')
    try {
      const me = await api.get('/auth/me')
      user.set(me)
      applyTheme(me.theme)
    } catch {
      user.set(null)
    } finally {
      loading = false
    }
  })

  function handleLogin(e) {
    user.set(e.detail)
    applyTheme(e.detail.theme)
    push('/')
  }
</script>

{#if loading}
  <div class="splash">
    <Loader2 size={34} class="spin" />
  </div>
{:else if !$user}
  <Login on:login={handleLogin} />
{:else}
  <div class="shell">
    <main class="content">
      <div class="container">
        <Router {routes} />
      </div>
    </main>

    <nav class="bottom-nav">
      <div class="nav-inner">
        {#each nav as item}
          <a
            href={'#' + item.path}
            class="nav-item"
            class:active={$location === item.path}
          >
            <svelte:component this={item.icon} size={22} />
            <span>{item.label}</span>
          </a>
        {/each}
      </div>
    </nav>
  </div>
{/if}

<Toasts />

<style>
  .splash { display: grid; place-items: center; height: 100vh; color: var(--accent); }
  :global(.spin) { animation: spin 0.9s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }

  .shell { min-height: 100vh; padding-bottom: 92px; }
  .content { padding: 22px 0 12px; }

  .bottom-nav {
    position: fixed; left: 0; right: 0; bottom: 0; z-index: 40;
    display: flex; justify-content: center;
    padding: 0 12px 12px;
    pointer-events: none;
  }
  .nav-inner {
    pointer-events: auto;
    display: flex; gap: 4px;
    background: var(--surface-strong);
    border: 1px solid var(--border-strong);
    backdrop-filter: var(--blur);
    -webkit-backdrop-filter: var(--blur);
    border-radius: 999px;
    padding: 7px;
    box-shadow: var(--shadow);
    width: 100%; max-width: 460px;
  }
  .nav-item {
    flex: 1;
    display: flex; flex-direction: column; align-items: center; gap: 3px;
    padding: 9px 6px; border-radius: 999px;
    color: var(--text-faint); font-size: 11px; font-weight: 600;
    transition: color var(--transition), background var(--transition);
  }
  .nav-item.active { color: #fff; background: var(--grad); }
  .nav-item:not(.active):hover { color: var(--text); }
</style>
