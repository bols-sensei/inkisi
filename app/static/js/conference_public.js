const cfg = (() => {
  try { return JSON.parse(document.getElementById('confdata').textContent); }
  catch (e) { return {}; }
})();

const $ = s => document.querySelector(s);

const renderBadgePreview = (container, src, alt, id = '') => {
  if (!container || !src) return;
  const image = document.createElement('img');
  image.className = 'premium-badge-image'; image.alt = alt;
  if (id) image.id = id;
  image.src = src;
  container.classList.add('badge-rendered');
  container.replaceChildren(image);
  if (!container.dataset.badgeMotion && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
    container.dataset.badgeMotion = 'true';
    container.addEventListener('pointermove', event => {
      const bounds = container.getBoundingClientRect();
      const x = (event.clientX - bounds.left) / bounds.width;
      const y = (event.clientY - bounds.top) / bounds.height;
      container.style.transform = `rotateY(${(x - .5) * 14}deg) rotateX(${(.5 - y) * 14}deg)`;
      container.style.setProperty('--gx', `${x * 100}%`);
      container.style.setProperty('--gy', `${y * 100}%`);
      container.style.setProperty('--go', '1');
    });
    container.addEventListener('pointerleave', () => {
      container.style.transform = '';
      container.style.setProperty('--go', '0');
    });
  }
};

if (cfg.mode === 'manage') {
  const card = document.querySelector('.badge-card');
  const download = document.querySelector('a[href^="/api/public/conferences/badge/"]');
  if (card && download) renderBadgePreview(card, `${download.getAttribute('href')}.png`, 'Badge premium avec QR code sécurisé', 'manageBadgeImage');
}

const box = (id, cls, text) => {
  const m = $(id);
  if (!m) return;
  m.className = 'banner ' + cls;
  m.textContent = text;
};

const post = async (url, method, body) => {
  const r = await fetch(url, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  let j = {};
  try { j = await r.json(); } catch (e) { /* empty */ }
  return { ok: r.ok, status: r.status, j };
};

const detail = j => (typeof j.detail === 'string' ? j.detail : 'Veuillez vérifier les champs du formulaire.');

// Redimensionne et compresse l'image côté client sur un canvas offscreen
const downscaleImage = (dataUrl, maxDim = 500, quality = 0.85) => {
  return new Promise(resolve => {
    const img = new Image();
    img.onload = () => {
      let w = img.width, h = img.height;
      if (w > maxDim || h > maxDim) {
        if (w > h) { h = Math.round((h * maxDim) / w); w = maxDim; }
        else { w = Math.round((w * maxDim) / h); h = maxDim; }
      }
      const canvas = document.createElement('canvas');
      canvas.width = w;
      canvas.height = h;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(img, 0, 0, w, h);
      resolve(canvas.toDataURL('image/jpeg', quality));
    };
    img.onerror = () => resolve(dataUrl);
    img.src = dataUrl;
  });
};

if (cfg.mode === 'register' && $('#f')) {
  const photoInput = $('#photoInput');
  const photoData = $('#photoData');
  const avatarPreview = $('#avatarPreview');
  const avatarImg = $('#avatarImg');
  const cameraIcon = $('#cameraIcon');
  const chooseBtn = $('#choosePhotoBtn');
  const removeBtn = $('#removePhotoBtn');

  const openPicker = () => photoInput && photoInput.click();

  if (avatarPreview) {
    avatarPreview.addEventListener('click', openPicker);
    avatarPreview.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openPicker(); }
    });
  }
  if (chooseBtn) chooseBtn.addEventListener('click', openPicker);

  if (photoInput) {
    photoInput.addEventListener('change', async () => {
      const file = photoInput.files && photoInput.files[0];
      if (!file) return;
      if (!file.type.startsWith('image/')) {
        box('#msg', 'bad', 'Veuillez choisir un fichier image valide (JPG, PNG).');
        return;
      }
      const reader = new FileReader();
      reader.onload = async e => {
        const optimized = await downscaleImage(e.target.result);
        photoData.value = optimized;
        avatarImg.src = optimized;
        avatarImg.classList.remove('hidden');
        if (cameraIcon) cameraIcon.classList.add('hidden');
        if (avatarPreview) avatarPreview.classList.add('has-photo');
        if (removeBtn) removeBtn.classList.remove('hidden');
        if (chooseBtn) chooseBtn.textContent = 'Changer la photo';
      };
      reader.readAsDataURL(file);
    });
  }

  if (removeBtn) {
    removeBtn.addEventListener('click', () => {
      if (photoInput) photoInput.value = '';
      if (photoData) photoData.value = '';
      if (avatarImg) { avatarImg.src = ''; avatarImg.classList.add('hidden'); }
      if (cameraIcon) cameraIcon.classList.remove('hidden');
      if (avatarPreview) avatarPreview.classList.remove('has-photo');
      removeBtn.classList.add('hidden');
      if (chooseBtn) chooseBtn.textContent = 'Ajouter une photo';
    });
  }

  // Soumission du formulaire d'inscription
  $('#f').onsubmit = async e => {
    e.preventDefault();
    const btn = $('#submitBtn');
    if (btn) { btn.disabled = true; btn.classList.add('busy'); }

    const raw = Object.fromEntries(new FormData(e.target));
    const payload = {
      last_name: (raw.last_name || '').trim(),
      first_name: (raw.first_name || '').trim(),
      full_name: `${(raw.first_name || '').trim()} ${(raw.last_name || '').trim()}`.trim(),
      email: (raw.email || '').trim(),
      phone: (raw.phone || '').trim(),
      profession: (raw.profession || '').trim(),
      organization_name: (raw.organization_name || '').trim(),
      photo_data: photoData ? photoData.value : null
    };

    try {
      const { ok, status, j } = await post(`/api/public/conferences/${cfg.token}/register`, 'POST', payload);
      if (!ok) {
        box('#msg', 'bad', detail(j));
      } else {
        // Succès : masquer le formulaire et afficher immédiatement le badge
        const form = $('#f');
        const badgeResult = $('#badgeResult');
        const programSection = $('#programSection');
        if (form) form.classList.add('hidden');
        if (programSection) programSection.classList.add('hidden');

        if (badgeResult && j.registration) {
          const reg = j.registration;
          const nameEl = $('#resFullName');
          const profEl = $('#resProf');
          const orgEl = $('#resOrg');
          const qrImg = $('#resQrImg');
          const photoImg = $('#resPhotoImg');
          const placeholder = $('#resPhotoPlaceholder');
          const downloadBtn = $('#resDownloadBtn');
          const footEl = $('#resFoot');
          const categoryEl = $('#resCategory');

          if (nameEl) nameEl.textContent = reg.full_name;
          if (profEl) profEl.textContent = reg.profession || '';
          if (orgEl) orgEl.textContent = reg.organization_name || '';
          if (categoryEl) categoryEl.textContent = (reg.category || 'participant').toUpperCase();
          if (qrImg) qrImg.src = `/api/public/conferences/badge-qr/${j.public_token}.png`;
          if (footEl) footEl.textContent = `BADGE OFFICIEL · RÉF ${reg.badge_reference}`;

          if (reg.photo_data && photoImg) {
            photoImg.src = reg.photo_data;
            photoImg.classList.remove('hidden');
            if (placeholder) placeholder.classList.add('hidden');
          } else {
            if (photoImg) photoImg.classList.add('hidden');
            if (placeholder) placeholder.classList.remove('hidden');
          }

          if (downloadBtn && j.badge_url) {
            downloadBtn.href = j.badge_url;
            renderBadgePreview(badgeResult.querySelector('.badge-card'), `${j.badge_url}.png`, `Badge premium de ${reg.full_name} avec QR code sécurisé`, 'resBadgeImage');
          }

          badgeResult.classList.remove('hidden');
          badgeResult.scrollIntoView({ behavior: 'smooth' });
        } else {
          const result = $('#registrationResult');
          const message = $('#registrationMessage');
          const link = $('#registrationManageLink');
          const note = $('#registrationSaveNote');
          if (message) message.textContent = j.message || 'Votre demande a été enregistrée.';
          if (link && j.registration_url) {
            link.href = j.registration_url;
            link.classList.remove('hidden');
          } else if (link) {
            link.classList.add('hidden');
          }
          if (note) note.classList.toggle('hidden', !j.registration_url);
          if (result) {
            result.classList.remove('hidden');
            result.scrollIntoView({ behavior: 'smooth' });
          }
        }
      }
    } catch (err) {
      box('#msg', 'bad', 'Erreur de connexion. Veuillez réessayer.');
    } finally {
      if (btn) { btn.disabled = false; btn.classList.remove('busy'); }
    }
  };

  const resetRegistration = () => {
      const form = $('#f');
      const badgeResult = $('#badgeResult');
      const registrationResult = $('#registrationResult');
      const programSection = $('#programSection');
      if (form) {
        form.reset();
        if (removeBtn) removeBtn.click();
        form.classList.remove('hidden');
      }
      if (badgeResult) badgeResult.classList.add('hidden');
      if (registrationResult) registrationResult.classList.add('hidden');
      if (programSection) programSection.classList.remove('hidden');
      window.scrollTo({ top: 0, behavior: 'smooth' });
  };
  $('#newRegBtn')?.addEventListener('click', resetRegistration);
  $('#newRequestBtn')?.addEventListener('click', resetRegistration);
}

// Gestion de la modification autonome par le participant (mode manage)
if (cfg.mode === 'manage' && $('#manageForm')) {
  $('#manageForm').onsubmit = async e => {
    e.preventDefault();
    const btn = $('#manageSubmitBtn');
    if (btn) { btn.disabled = true; btn.classList.add('busy'); }

    const raw = Object.fromEntries(new FormData(e.target));
    const payload = {
      last_name: (raw.last_name || '').trim(),
      first_name: (raw.first_name || '').trim(),
      full_name: `${(raw.first_name || '').trim()} ${(raw.last_name || '').trim()}`.trim(),
      phone: (raw.phone || '').trim(),
      profession: (raw.profession || '').trim(),
      organization_name: (raw.organization_name || '').trim()
    };

    try {
      const { ok, j } = await post(`/api/public/conferences/registration/${cfg.regToken}`, 'PATCH', payload);
      if (!ok) {
        box('#manageMsg', 'bad', detail(j));
      } else {
        box('#manageMsg', 'ok', j.message || 'Vos informations ont été mises à jour avec succès.');
        // Mise à jour de l'affichage local du badge
        const badgeName = document.querySelector('.badge-card .badge-name');
        if (badgeName && payload.full_name) badgeName.textContent = payload.full_name;
        const badgeImage = $('#manageBadgeImage');
        if (badgeImage) badgeImage.src = `/api/public/conferences/badge/${cfg.regToken}.png?updated=${Date.now()}`;
      }
    } catch (err) {
      box('#manageMsg', 'bad', 'Erreur lors de la mise à jour.');
    } finally {
      if (btn) { btn.disabled = false; btn.classList.remove('busy'); }
    }
  };
}
