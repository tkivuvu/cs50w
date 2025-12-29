document.addEventListener('DOMContentLoaded', function() {

  // Use buttons to toggle between views
  document.querySelector('#inbox').addEventListener('click', () => load_mailbox('inbox'));
  document.querySelector('#sent').addEventListener('click', () => load_mailbox('sent'));
  document.querySelector('#archived').addEventListener('click', () => load_mailbox('archive'));
  document.querySelector('#compose').addEventListener('click', () => compose_email());

  // Compose form and submit
  const composeForm = document.querySelector('#compose-form');
  if (composeForm) {
    composeForm.addEventListener('submit', function (event) {
      event.preventDefault();

      const recipients = document.querySelector('#compose-recipients').value.trim();
      const subject = document.querySelector('#compose-subject').value.trim();
      const body = document.querySelector('#compose-body').value;

      if (!recipients) {
        alert('At least one recipient is required.');
        return;
      }

      const submitBtn = event.submitter || composeForm.querySelector('[type="submit"]');
      if (submitBtn) submitBtn.disabled = true;

      fetch('/emails', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ recipients, subject, body })
      })
      .then(response => response.json().then(data => ({ ok: response.ok, data })))
      .then(({ ok, data }) => {
        if (submitBtn) submitBtn.disabled = false;

        if (!ok || data.error) {
          alert(data.error || 'Failure occured trying to send email.');
          return;
        }

        load_mailbox('sent');
      })
      .catch(() => {
        if (submitBtn) submitBtn.disabled = false;
        alert('An issue with the network occured whilst trying to send, please try again.')
      });
    });
  }

  // By default, load the inbox
  load_mailbox('inbox');
});


function compose_email({ recipients = '', subject = '', body = '' } = {}) {

  // Show compose view and hide other views
  document.querySelector('#emails-view').style.display = 'none';
  document.querySelector('#compose-view').style.display = 'block';
  const detail = document.querySelector('#view-email');
  if (detail) detail.style.display = 'none';

  // Clear out composition fields or prefill them if called with prefill object
  document.querySelector('#compose-recipients').value = recipients;
  document.querySelector('#compose-subject').value = subject;
  document.querySelector('#compose-body').value = body;

  document.querySelector('#compose-recipients').focus();
}


function load_mailbox(mailbox) {

  // Show the mailbox and hide other views
  document.querySelector('#emails-view').style.display = 'block';
  document.querySelector('#compose-view').style.display = 'none';
  const detail = document.querySelector('#view-email');
  if (detail) detail.style.display = 'none';

  const view = document.querySelector('#emails-view');

  // Show the mailbox name
  document.querySelector('#emails-view').innerHTML = `<h3>${mailbox.charAt(0).toUpperCase() + mailbox.slice(1)}</h3>`;

  fetch(`/emails/${mailbox}`)
    .then(response => response.json())
    .then(emails => {
      if (!Array.isArray(emails) || emails.length == 0) {
        const p = document.createElement('p');
        p.textContent = 'No emails.';
        p.style.opacity = '0.7';
        view.append(p);
        return;
      }

      emails.forEach(email => {
        const box = document.createElement('div');
        box.className = `email-row ${email.read ? 'read' : 'unread'}`;

        const primary = (mailbox === 'sent')
          ?  `To: ${email.recipients.join(', ')}`
          : email.sender;

        const who = document.createElement('div');
        who.className = 'who';
        const strong = document.createElement('strong');
        strong.textContent = primary;
        who.append(strong);

        const subj = document.createElement('div');
        subj.className = 'subject';
        subj.textContent = email.subject || '(no subject)';

        const time = document.createElement('div');
        time.className = 'time';
        time.textContent = email.timestamp;

        box.addEventListener('click', function () {
          view_email(email.id, mailbox);
        });

        box.append(who, subj, time);
        view.append(box);
      });
    })
    .catch(() => {
      const err = document.createElement('p');
      err.textContent = 'Failure to load mailbox';
      err.className = 'error';
      const view = document.querySelector('#emails-view');
      view.append(err);
    })
}


function view_email(email_id, mailbox) {
  //views toggle
  document.querySelector('#emails-view').style.display = 'none';
  document.querySelector('#compose-view').style.display = 'none';
  const detail = document.querySelector('#view-email');
  detail.style.display = 'block';
  detail.innerHTML = '';

  // GET email
  fetch(`/emails/${email_id}`)
    .then(response => response.json())
    .then(email => {
      // Mark read if need be
      if (!email.read) {
        fetch(`/emails/${email_id}`, {
          method: 'PUT',
          body: JSON.stringify({ read: true })
        });
      }

      // Header
      const h3 = document.createElement('h3');
      h3.textContent = 'Email';

      // From
      const from = document.createElement('div');
      const fromB = document.createElement('strong'); fromB.textContent = 'From: ';
      const fromSpan = document.createElement('span'); fromSpan.textContent = email.sender;
      from.append(fromB, fromSpan);

      // To
      const to = document.createElement('div');
      const toB = document.createElement('strong'); toB.textContent = 'To: ';
      const toSpan = document.createElement('span'); toSpan.textContent = email.recipients.join(', ');
      to.append(toB, toSpan);

      // Subject
      const subject = document.createElement('div');
      const subjB = document.createElement('strong'); subjB.textContent = 'Subject: ';
      const subjSpan = document.createElement('span'); subjSpan.textContent = email.subject || '(no subject)';
      subject.append(subjB, subjSpan);

      // Timestamp
      const time = document.createElement('div');
      const timeB = document.createElement('strong'); timeB.textContent = 'Timestamp: ';
      const timeSpan = document.createElement('span'); timeSpan.textContent = email.timestamp;
      time.append(timeB, timeSpan);

      // Specific controls for reply btn and (un)archive btn for non-sent
      const controls = document.createElement('div');
      controls.className = 'controls';

      // Reply button
      const replyBtn = document.createElement('button');
      replyBtn.className = 'btn btn-sm btn-outline-primary';
      replyBtn.textContent = 'Reply';
      replyBtn.addEventListener('click', function () {
        // Add "Re: " prefix to subject
        let subj = email.subject || '';
        if (!subj.trim().toLowerCase().startsWith('re: ')) {
          subj = 'Re: ' + subj;
        }
        // Quote original email
        const header = `"On ${email.timestamp} ${email.sender} wrote:\n`;
        const quoted = `${email.body || ''}"`;
        compose_email({
          recipients: email.sender,
          subject: subj,
          body: `\n\n${header}${quoted}`
        });
      });
      controls.append(replyBtn);

      // Archive/Unarchive (except for sent)
      if (mailbox !== 'sent') {
        const archBtn = document.createElement('button');
        archBtn.className = 'btn btn-sm btn-outline-primary';
        archBtn.textContent = email.archived ? 'Unarchive' : 'Archive';

        archBtn.addEventListener('click', function () {
          fetch(`/emails/${email_id}`, {
            method: 'PUT',
            body: JSON.stringify({ archived: !email.archived })
          })
          .then(() => {
            // load user mailbox after (un)archiving
            load_mailbox('inbox');
          })
          .catch(() => {
            alert('Failed to update archive status. Please try again.');
          });
        });

        controls.append(archBtn);
      }

      const hr = document.createElement('hr');

      const body = document.createElement('div');
      body.className = 'email-body';
      body.textContent = email.body || '';

      // Put together detail view
      detail.append(h3, from, to, subject, time, controls, hr, body);
    })
    .catch(() => {
      const err = document.createElement('p');
      err.textContent = 'Failed to load email';
      err.style.color = 'red';
      const detail = document.querySelector('#view-email');
      detail.append(err);
    });
}
