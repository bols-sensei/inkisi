/* Traitement local de la photo du badge membre ; aucun envoi avant le formulaire. */
const input = document.getElementById('memberPhoto');
if (input) {
  const data = document.getElementById('memberPhotoData');
  const preview = document.getElementById('memberPhotoPreview');
  const error = document.getElementById('memberPhotoError');
  input.addEventListener('change', () => {
    data.value = '';
    preview.classList.add('hidden');
    error.classList.add('hidden');
    const file = input.files?.[0];
    if (!file) return;
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size > 10 * 1024 * 1024) {
      error.textContent = 'Choisissez une image JPEG, PNG ou WebP de moins de 10 Mo.';
      error.classList.remove('hidden'); input.value = ''; return;
    }
    const reader = new FileReader();
    reader.onerror = () => { error.textContent = 'La photo n’a pas pu être lue.'; error.classList.remove('hidden'); };
    reader.onload = () => {
      const image = new Image();
      image.onerror = () => { error.textContent = 'Le fichier image est invalide.'; error.classList.remove('hidden'); };
      image.onload = () => {
        const size = Math.min(image.naturalWidth, image.naturalHeight, 400);
        const sx = (image.naturalWidth - size) / 2, sy = (image.naturalHeight - size) / 2;
        const canvas = document.createElement('canvas'); canvas.width = size; canvas.height = size;
        canvas.getContext('2d').drawImage(image, sx, sy, size, size, 0, 0, size, size);
        data.value = canvas.toDataURL('image/jpeg', 0.84);
        preview.src = data.value; preview.classList.remove('hidden');
      };
      image.src = reader.result;
    };
    reader.readAsDataURL(file);
  });
}
