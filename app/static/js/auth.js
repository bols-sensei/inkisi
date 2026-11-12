const form = document.querySelector('#registerForm');
if (form) {
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const button = form.querySelector('button[type="submit"]');
    const message = document.querySelector('#registerMessage');
    const data = Object.fromEntries(new FormData(form));
    button.disabled = true;
    button.textContent = 'Création en cours…';
    message.textContent = '';
    try {
      const response = await fetch('/api/organizations/register', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data)
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || 'Impossible de créer cette organisation.');
      const login = document.querySelector('.login-form');
      login.querySelector('[name="username"]').value = data.admin_username;
      message.className = 'banner ok';
      message.textContent = `${result.message} Connectez-vous avec votre nouvel identifiant.`;
      form.reset();
      login.querySelector('[name="password"]').focus();
    } catch (error) {
      message.className = 'banner bad';
      message.textContent = error.message;
    } finally {
      button.disabled = false;
      button.textContent = 'Démarrer mon essai gratuit de 14 jours';
    }
  });
}
