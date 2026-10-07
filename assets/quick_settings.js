/* Private settings and explicit worker/OAuth controls. No background work on GET. */
(() => {
  const $ = id => document.getElementById(id);
  const panel = $('qaSettings');
  if (!panel) return;
  let loaded = false, busy = false, timer = null, last = null;
  const announce = (message, error=false) => {
    $('qaSettingsStatus').textContent = message;
    $('qaSettingsStatus').className = error ? 'qa-error' : '';
  };
  async function request(path, data) {
    const response = await fetch('/api/quick-analyses/' + path, data === undefined ? {cache:'no-store'} :
      {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Agent-Einstellungen nicht erreichbar');
    return result;
  }
  function dateInput(value) {
    const date = value ? new Date(value) : new Date();
    if (Number.isNaN(date.getTime())) return '';
    return new Date(date.getTime()-date.getTimezoneOffset()*60000).toISOString().slice(0,16);
  }
  const dateValue = id => $(id).value ? new Date($(id).value).toISOString() : null;
  function number(id) {
    const text = $(id).value.trim().replace(/\s/g,'');
    if (!text) throw new Error('Finanzierungswerte vollständig eintragen');
    const value = Number(text.replace(/\.(?=\d{3}(?:\D|$))/g,'').replace(',','.'));
    if (!Number.isFinite(value)) throw new Error('Ungültige Zahl im Finanzierungsprofil');
    return value;
  }
  function visibility() {
    $('qaProfileFields').hidden = !$('qaProfileEnabled').checked;
    $('qaGmailFields').hidden = $('qaMailSource').value !== 'gmail';
    $('qaLocalFields').hidden = $('qaMailSource').value === 'gmail';
    $('qaEkLabel').textContent = $('qaEkMode').value === 'betrag' ? 'Eigenkapital (€)' : 'Eigenkapital (%)';
  }
  function fill(data) {
    const s = data.settings, p = s.profile;
    $('qaProfileEnabled').checked = !!p;
    $('qaProfileName').value = p?.name || '';
    $('qaEkMode').value = p?.ekModus || 'betrag';
    $('qaEkValue').value = p ? String(p.ekModus==='betrag' ? p.ek : p.ekAnteil) : '';
    $('qaInterest').value = p ? String(p.zins) : '';
    $('qaRepayment').value = p ? String(p.tilgung) : '';
    $('qaMailSource').value = s.source;
    $('qaMailDirectory').value = s.mail_directory;
    $('qaMailQuery').value = s.query;
    $('qaSenders').value = s.senders.join('\n');
    $('qaSubjects').value = s.subjects.join('\n');
    $('qaMailStart').value = dateInput(s.start_at);
    $('qaInterval').value = s.interval;
    $('qaConcurrency').value = s.concurrency;
    $('qaTelegramEnabled').checked = s.telegram_enabled;
    $('qaAutoSend').checked = s.auto_send_new;
    $('qaChatId').value = s.chat_id;
    $('qaSendStart').value = dateInput(s.send_start_at);
    visibility();
  }
  function status(data) {
    const completed = last?.worker.running && !data.worker.running;
    last = data;
    const operations = Object.values(data.operations);
    const active = operations.some(x => ['queued','running'].includes(x.state));
    const running = data.worker.running;
    $('qaEditable').disabled = running || active || busy;
    $('qaSaveSettings').disabled = running || active || busy;
    $('qaGoogleClient').disabled = running || active || busy;
    $('qaInstallGmail').disabled = running || active || busy || data.gmail.dependencies_ready;
    $('qaAuthorizeGmail').disabled = running || active || busy || !data.gmail.client_ready || !data.gmail.dependencies_ready;
    $('qaStartWorker').disabled = running || active || busy || !data.configuration_saved;
    $('qaCheckOnce').disabled = running || active || busy || !data.configuration_saved;
    $('qaStopWorker').disabled = !data.worker.managed || data.worker.stopping || busy;
    $('qaWorkerState').textContent = data.worker.label + (data.worker.last_poll ? ' · Letzte Prüfung: '+new Date(data.worker.last_poll).toLocaleString('de-DE') : '') + (!data.node_ready ? ' · Node.js fehlt' : '');
    $('qaGmailSetupState').textContent = [data.gmail.client_ready ? 'Desktop-Client gespeichert' : 'Desktop-Client fehlt',
      data.gmail.dependencies_ready ? 'Komponenten bereit' : 'Komponenten fehlen',data.connections.gmail,
      ...operations.filter(x=>x.state).map(x=>x.message)].join(' · ');
    $('qaTelegramSaved').textContent = (data.settings.telegram_token_saved ? 'Bot-Token privat gespeichert. ' : '') +
      (data.pending_sends ? data.pending_sends+' offene Versandaufträge: vor Live-Aktivierung prüfen.' : 'Keine offenen Versandaufträge.');
    if(completed)document.dispatchEvent(new Event('qa-settings-changed'));
    if (!data.private_storage) announce('Die gewählte Konfiguration liegt im Projektordner. Für die Einrichtung eine private Konfiguration außerhalb des Repositories verwenden.',true);
  }
  async function refresh(fillForm=false) {
    try {
      const data = await request('settings');
      if (fillForm || !loaded) {fill(data);loaded=true;}
      status(data);
    } catch(error) {announce(error.message,true);}
  }
  async function act(action) {
    busy=true;if(last)status(last);
    try {
      const data=await request('control',{action});status(data);
      announce(action==='stop-worker' ? 'Stop angefordert; laufende Jobs werden beendet.' :
        action==='authorize-gmail' ? 'Google-Anmeldung im Browser abschließen.' :
        action==='install-gmail' ? 'Gmail-Komponenten werden in einer privaten Python-Umgebung installiert.' : 'Verarbeitung gestartet. Anschließend Schnellanalysen aktualisieren.');
      document.dispatchEvent(new Event('qa-settings-changed'));
    } catch(error) {announce(error.message,true);}
    finally {busy=false;await refresh();}
  }
  $('qaSettingsForm').addEventListener('submit',async event=>{
    event.preventDefault();busy=true;if(last)status(last);
    try {
      let profile=null;
      if($('qaProfileEnabled').checked) {
        if(!$('qaProfileName').value.trim())throw new Error('Profilname eintragen');
        profile={name:$('qaProfileName').value.trim(),ekModus:$('qaEkMode').value,zins:number('qaInterest'),tilgung:number('qaRepayment')};
        profile[profile.ekModus==='betrag' ? 'ek' : 'ekAnteil']=number('qaEkValue');
      }
      const lines=id=>$(id).value.split(/[,;\n]/).map(x=>x.trim()).filter(Boolean);
      const values={profile,source:$('qaMailSource').value,interval:Number($('qaInterval').value),concurrency:Number($('qaConcurrency').value),
        mail_directory:$('qaMailDirectory').value,query:$('qaMailQuery').value,senders:lines('qaSenders'),subjects:lines('qaSubjects'),start_at:dateValue('qaMailStart'),
        telegram_enabled:$('qaTelegramEnabled').checked,auto_send_new:$('qaAutoSend').checked,send_start_at:dateValue('qaSendStart'),chat_id:$('qaChatId').value,bot_token:$('qaBotToken').value};
      const data=await request('settings',values);fill(data);status(data);$('qaBotToken').value='';
      announce('Einstellungen privat gespeichert. Bestehende Analysen bleiben unverändert.');
      document.dispatchEvent(new Event('qa-settings-changed'));
    }catch(error){announce(error.message,true);}
    finally{busy=false;await refresh();}
  });
  $('qaGoogleClient').addEventListener('change',async event=>{
    const file=event.target.files[0];if(!file)return;
    busy=true;if(last)status(last);
    try {
      if(file.size>100000)throw new Error('OAuth-Datei zu groß');
      const data=await request('gmail-client',{client:JSON.parse(await file.text())});status(data);
      announce('Desktop-Client privat gespeichert. Als Nächstes Komponenten einrichten und mit Google anmelden.');
    }catch(error){announce(error.message,true);}
    finally{event.target.value='';busy=false;await refresh();}
  });
  for(const [id,action] of Object.entries({qaInstallGmail:'install-gmail',qaAuthorizeGmail:'authorize-gmail',qaStartWorker:'start-worker',qaStopWorker:'stop-worker',qaCheckOnce:'check-once'})) {
    $(id).addEventListener('click',()=>act(action));
  }
  for(const id of ['qaProfileEnabled','qaMailSource','qaEkMode'])$(id).addEventListener('change',visibility);
  if(location.hash==='#qaSettings')panel.open=true;
  panel.addEventListener('toggle',()=>{
    if(timer){clearInterval(timer);timer=null;}
    if(panel.open){refresh();timer=setInterval(()=>{if(!busy)refresh();},2000);}
  });
})();
