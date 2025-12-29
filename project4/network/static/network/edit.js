function getCookie(name) {
    const m = document.cookie.match(
        '(?:^|; )' + name.replace(/([.$?*|{}()\[\]\\\/\+^])/g, '\\$1') + '=([^;]*)');
        return m ? decodeURIComponent(m[1]) : null;
}
const csrftoken = getCookie('csrftoken');

function qs(sel, root = document){ return root.querySelector(sel); }

function enterEdit(postId) {
    const p = qs(`#post-content-${postId}`);
    if (!p) return;

    if (qs(`#post-editor-${postId}`)) return;

    const original = p.textContent;

    const wrap = document.createElement('div');
    wrap.id = `post-editor-${postId}`;

    const ta = document.createElement('textarea');
    ta.value = original;
    ta.rows = 3;
    ta.maxLength = 500;
    ta.className = 'form-control mb-2';

    const counter = document.createElement('small');
    counter.className = 'text-muted d-block mb-2';
    const updateCount = () => { counter.textContent = `${ta.value.length} / 500`; };
    ta.addEventListener('input', updateCount);
    updateCount();

    const saveBtn = document.createElement('button');
    saveBtn.type = 'button';
    saveBtn.className = 'btn btn-sm btn-primary mr-2';
    saveBtn.textContent = 'Save';

    const cancelBtn = document.createElement('button');
    cancelBtn.type = 'button';
    cancelBtn.className = 'btn btn-sm btn-secondary';
    cancelBtn.textContent = 'Cancel';

    const err = document.createElement('div');
    err.className = 'text-danger small mb-2';
    err.style.display = 'none';

    wrap.append(ta, counter, err, saveBtn, cancelBtn);

    p.after(wrap);
    p.style.display = 'none';

    const editLink = qs(`#post-edit-${postId}`);
    if (editLink) editLink.style.display = 'none';

    const showError = (msg) => {
        err.textContent = msg || 'Failed to save changes.';
        err.style.display = '';
    }

    saveBtn.addEventListener('click', async () => {
        const content = ta.value.trim();
        if (!content) { showError('Post cannot be empty.'); return; }
        if (content.length > 500) { showError('Posts have a 500 character limit.'); return; }

        saveBtn.disabled = true; cancelBtn.disabled = true; err.style.display = 'none';
        try {
            const res = await fetch(`/api/posts/${postId}/edit/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrftoken,
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({ content })
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                showError(data.error || `Error ${res.status}`);
                throw new Error(data.error || 'Failed');
            }
            p.textContent = data.content;
            const edited = qs(`#post-edited-${postId}`);
            if (edited) edited.classList.remove('d-none');
            exitEdit(postId);
        } catch (e) {
          // console.error('Edit failed', e);
        } finally {
          saveBtn.disabled = false; cancelBtn.disabled = false;
        }
    });

    cancelBtn.addEventListener('click', () => {
        exitEdit(postId);
    });
}

function exitEdit(postId) {
    const p = qs(`#post-content-${postId}`);
    const editor = qs(`#post-editor-${postId}`);
    const editLink = qs(`#post-edit-${postId}`);
    if (editor) editor.remove();
    if (p) p.style.display = '';
    if (editLink) editLink.style.display = '';
}

addEventListener('click', (e) => {
    const link = e.target.closest('.post-edit-link');
    if (!link) return;
    e.preventDefault();
    const postId = link.dataset.postId;
    if (postId) enterEdit(postId);
});
