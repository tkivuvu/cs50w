function getCookieLike(name) {
    const m = document.cookie.match(
        '(?:^|; )' + name.replace(/([.$?*|{}()\[\]\\\/\+^])/g, '\\$1') + '=([^;]*)');
        return m ? decodeURIComponent(m[1]) : null;
}
const csrfToken = getCookieLike('csrftoken');

function pluralize(n) { return n === 1 ? '' : 's'; }

addEventListener('click', async (e) => {
    const btn = e.target.closest('.post-like-btn');
    if (!btn) return;
    e.preventDefault();
    const postId = btn.dataset.postId;
    if (!postId) return;

    btn.disabled = true;
    try {
        const res = await fetch(`/api/posts/${postId}/like/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken,
                'X-Requested-With': 'XMLHttpRequest',
            }
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.error || `Error ${res.status}`);

        const countEl = document.getElementById(`post-likes-${postId}`);
        const suffixEl = document.getElementById(`post-likes-suffix-${postId}`);

        if (countEl) countEl.textContent = data.likes;
        if (suffixEl) suffixEl.textContent = pluralize(data.likes);

        btn.setAttribute('aria-pressed', data.liked ? 'true' : 'false');
        btn.textContent = data.liked ? 'Unlike' : 'Like';
    } catch (err) {
    } finally {
        btn.disabled = false;
    }
});
