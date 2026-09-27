/* Object pages read and write only the local SQLite API. */
(() => {
  const sessions = new Map();
  const url = name => `/api/objects/${encodeURIComponent(name)}`;
  async function responseJson(response) {
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const error = new Error(data.error || `HTTP ${response.status}`);
      error.status = response.status;
      throw error;
    }
    return data;
  }
  async function load(name) {
    const data = await responseJson(await fetch(url(name), {cache: 'no-store'}));
    sessions.set(name, {id:data.id, revision:data.revision, busy:false, dirty:false, timer:null, pending:null});
    return data;
  }
  async function flush(name) {
    const session = sessions.get(name);
    if (!session) throw new Error('Objekt noch nicht aus der Datenbank geladen');
    clearTimeout(session.timer);
    if (session.busy) return session.pending;
    session.busy = true;
    session.pending = (async () => {
      while (session.dirty) {
        session.dirty = false;
        session.status('saving');
        try {
          const data = await responseJson(await fetch(url(session.id), {
            method:'PUT', headers:{'Content-Type':'application/json'},
            body:JSON.stringify({revision:session.revision, state:session.getState()})
          }));
          session.revision = data.revision;
          session.status('saved', data.revision);
          if ('BroadcastChannel' in window) {
            const channel = new BroadcastChannel('immo-db-revision');
            channel.postMessage({name, revision:data.revision});
            channel.close();
          }
        } catch (error) {
          session.dirty = false;
          session.status(error.status === 409 ? 'conflict' : 'error', error.message);
          throw error;
        }
      }
    })();
    try { return await session.pending; }
    finally { session.busy = false; session.pending = null; }
  }
  function schedule(name, getState, status) {
    const session = sessions.get(name);
    if (!session) return;
    session.getState = getState;
    session.status = status;
    session.dirty = true;
    clearTimeout(session.timer);
    session.timer = setTimeout(() => { flush(name).catch(() => {}); }, 400);
  }
  async function exportJson(name) {
    await flush(name);
    const data = await responseJson(await fetch(`/api/export/${encodeURIComponent(name)}`, {cache:'no-store'}));
    const blob = new Blob([JSON.stringify(data, null, 2)], {type:'application/json'});
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `${name}_Übersicht_State.json`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 1000);
  }
  async function setArchived(name, archive) {
    await flush(name);
    const session = sessions.get(name);
    const response = await fetch(`${url(session.id)}/${archive ? 'archive' : 'reactivate'}`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({revision:session.revision})
    });
    return responseJson(response);
  }
  async function uploadPhoto(name, file) {
    if (!file || file.size > 5_000_000 || !['image/jpeg','image/png','image/webp','image/avif'].includes(file.type)) {
      throw new Error('Bitte JPEG, PNG, WebP oder AVIF bis 5 MB wählen');
    }
    await flush(name);
    const session = sessions.get(name);
    const dataUrl = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
    const response = await fetch(`${url(session.id)}/photo`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({revision:session.revision, mime:file.type, data:String(dataUrl).split(',')[1]})
    });
    const result = await responseJson(response);
    session.revision = result.revision;
    if ('BroadcastChannel' in window) {
      const channel = new BroadcastChannel('immo-db-revision');
      channel.postMessage({name, revision:result.revision});
      channel.close();
    }
    return result;
  }
  window.ImmoDb = {load, schedule, flush, exportJson, setArchived, uploadPhoto};
  document.addEventListener('DOMContentLoaded', () => {
    const button = document.getElementById('archiveBtn');
    if (!button || typeof OBJEKT_ORDNER === 'undefined') return;
    const photoButton = document.createElement('button');
    photoButton.type = 'button';
    photoButton.className = 'btn secondary';
    photoButton.textContent = '🖼️ Objektfoto hinzufügen';
    const photoInput = document.createElement('input');
    photoInput.type = 'file';
    photoInput.accept = 'image/jpeg,image/png,image/webp,image/avif';
    photoInput.hidden = true;
    photoButton.onclick = () => photoInput.click();
    photoInput.onchange = async () => {
      photoButton.disabled = true;
      try {
        const result = await uploadPhoto(OBJEKT_ORDNER, photoInput.files[0]);
        const image = document.getElementById('objectPhoto');
        const figure = document.getElementById('objectHero');
        if (image && figure) {
          image.src = result.image_path + '?revision=' + result.revision;
          figure.hidden = false;
        }
        document.getElementById('savedNote').textContent = `DB-Revision ${result.revision}`;
      } catch (error) { alert('Foto konnte nicht gespeichert werden: ' + error.message); }
      finally { photoButton.disabled = false; photoInput.value = ''; }
    };
    button.before(photoButton, photoInput);
    const archive = !location.pathname.includes('/_ARCHIV/');
    button.textContent = archive ? '🗄️ Archivieren' : '↩️ Reaktivieren';
    button.onclick = async () => {
      if (!confirm(`${OBJEKT_ORDNER} ${archive ? 'archivieren' : 'reaktivieren'}?`)) return;
      button.disabled = true;
      try {
        await setArchived(OBJEKT_ORDNER, archive);
        location.href = '/portfolio.html';
      } catch (error) {
        alert('Statusänderung fehlgeschlagen: ' + error.message);
        button.disabled = false;
      }
    };
  });
})();
