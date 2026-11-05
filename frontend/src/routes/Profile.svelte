<script>
  import { Loader2, LogOut, Sun, Moon, Check, Download, Upload } from 'lucide-svelte'
  import { api } from '../lib/api.js'
  import { user, applyTheme, toast } from '../lib/stores.js'
  import { AVATAR_KEYS } from '../lib/avatars.js'
  import Avatar from '../components/Avatar.svelte'

  let displayName = $user.display_name
  let avatar = $user.avatar
  let reportCurrency = $user.report_currency
  let savingProfile = false

  let curPass = ''
  let newPass = ''
  let savingPass = false

  async function saveProfile() {
    savingProfile = true
    try {
      const updated = await api.patch('/profile', {
        display_name: displayName,
        avatar,
        report_currency: reportCurrency
      })
      user.set({ ...$user, ...updated })
      toast('Профиль сохранён', 'success')
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      savingProfile = false
    }
  }

  async function setTheme(t) {
    applyTheme(t)
    localStorage.setItem('bp_theme', t)
    try {
      await api.patch('/profile', { theme: t })
      user.set({ ...$user, theme: t })
    } catch (e) {
      toast(e.message, 'error')
    }
  }

  async function changePassword() {
    if (newPass.length < 4) { toast('Новый пароль слишком короткий', 'error'); return }
    savingPass = true
    try {
      await api.post('/profile/password', { current_password: curPass, new_password: newPass })
      toast('Пароль изменён', 'success')
      curPass = newPass = ''
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      savingPass = false
    }
  }

  let restoring = false

  async function restore(e) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    if (!confirm('Заменить текущие счета, операции и долги данными из файла? Логины и пароли останутся прежними.')) return
    restoring = true
    try {
      const res = await fetch('/api/profile/restore', { method: 'POST', body: file, credentials: 'same-origin' })
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Не удалось восстановить')
      toast('Данные восстановлены', 'success')
      location.reload()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      restoring = false
    }
  }

  async function logout() {
    try { await api.post('/auth/logout') } catch {}
    user.set(null)
    location.hash = '#/'
  }

  $: dirty =
    displayName !== $user.display_name ||
    avatar !== $user.avatar ||
    reportCurrency !== $user.report_currency
</script>

<h2 class="title fade-up">Профиль</h2>

<div class="card block">
  <div class="avatar-head">
    <Avatar name={avatar} size={72} />
    <div>
      <div style="font-weight:700;font-size:18px">{displayName || $user.display_name}</div>
      <div class="dim" style="font-size:13px">@{$user.username}</div>
    </div>
  </div>

  <div class="field">
    <span class="lbl">Аватар</span>
    <div class="avatars">
      {#each AVATAR_KEYS as key}
        <button class="av-opt" class:sel={avatar === key} on:click={() => (avatar = key)}>
          <Avatar name={key} size={44} />
        </button>
      {/each}
    </div>
  </div>

  <div class="field">
    <label for="dn">Имя</label>
    <input id="dn" bind:value={displayName} maxlength="40" />
  </div>

  <div class="field">
    <span class="lbl">Валюта отчётов</span>
    <div class="segmented">
      <button class:active={reportCurrency === 'BYN'} on:click={() => (reportCurrency = 'BYN')}>Br · BYN</button>
      <button class:active={reportCurrency === 'USD'} on:click={() => (reportCurrency = 'USD')}>$ · USD</button>
    </div>
  </div>

  <button class="btn btn-primary" on:click={saveProfile} disabled={savingProfile || !dirty}>
    {#if savingProfile}<Loader2 size={17} class="spin" />{:else}<Check size={17} />{/if} Сохранить
  </button>
</div>

<div class="card block">
  <h3>Оформление</h3>
  <div class="segmented theme">
    <button class:active={$user.theme === 'dark'} on:click={() => setTheme('dark')}><Moon size={16} /> Тёмная</button>
    <button class:active={$user.theme === 'light'} on:click={() => setTheme('light')}><Sun size={16} /> Светлая</button>
  </div>
</div>

<div class="card block">
  <h3>Смена пароля</h3>
  <div class="field">
    <label for="cp">Текущий пароль</label>
    <input id="cp" type="password" bind:value={curPass} autocomplete="current-password" />
  </div>
  <div class="field">
    <label for="np">Новый пароль</label>
    <input id="np" type="password" bind:value={newPass} autocomplete="new-password" />
  </div>
  <button class="btn" on:click={changePassword} disabled={savingPass || !curPass || !newPass}>
    {#if savingPass}<Loader2 size={17} class="spin" />{/if} Изменить пароль
  </button>
</div>

<div class="card block">
  <h3>Копия базы</h3>
  <p class="dim" style="font-size:13px">
    Скачивается файл SQLite со всеми операциями. При восстановлении счета, категории, долги
    и операции заменяются данными из файла; логины, пароли и текущий вход остаются.
    Старым копиям недостающие поля добавляются автоматически.
  </p>
  <a class="btn" href="/api/profile/backup" style="text-decoration:none"><Download size={17} /> Скачать backup</a>
  <label class="btn" class:disabled={restoring}>
    {#if restoring}<Loader2 size={17} class="spin" />{:else}<Upload size={17} />{/if}
    Восстановить из файла
    <input type="file" accept=".db,.sqlite,.sqlite3,application/octet-stream" on:change={restore} disabled={restoring} hidden />
  </label>
</div>

<button class="btn logout" on:click={logout}><LogOut size={17} /> Выйти из аккаунта</button>

<style>
  .title { font-size: 22px; font-weight: 800; margin-bottom: 16px; }
  .block { padding: 20px; margin-bottom: 16px; display: flex; flex-direction: column; gap: 16px; }
  .block h3 { font-size: 15px; font-weight: 700; }
  .avatar-head { display: flex; align-items: center; gap: 16px; }
  .avatars { display: flex; flex-wrap: wrap; gap: 10px; }
  .av-opt { background: none; border: 2px solid transparent; border-radius: 50%; padding: 2px; transition: border-color var(--transition); line-height: 0; }
  .av-opt.sel { border-color: var(--accent); }
  .segmented { width: 100%; }
  .segmented button { flex: 1; }
  .theme button { gap: 7px; }
  label.btn { cursor: pointer; }
  label.btn.disabled { opacity: 0.5; pointer-events: none; }
  .logout { width: 100%; color: var(--neg); border-color: rgba(244,63,94,0.25); }
  .logout:hover { background: rgba(244,63,94,0.1); }
</style>
