/* H-BOTdetector page logic.
   The full check is done by the server (POST /api/check).
   If the server cannot answer, the quick check below answers instead,
   under the same governing rule: an unanticipated message is presumed a scam. */

var HBotRules = (function () {
  var A = "[’']";
  // id, kind shown to the reader, pattern, weight, plain reason
  var rules = [
    ['credentials', 'Request for your codes or passwords', /\b(?:send|share|give|provide|enter|confirm|verify|tell)\b[\s\S]{0,70}\b(?:password|PIN|verification code|one[- ]time (?:code|password)|OTP|social security number|bank details|card number|seed phrase)\b/i, 3, 'It asks for a password, a code or account details. Nobody genuine asks for those in a message.'],
    ['investment', 'Investment pitch', /\b(guaranteed (?:returns?|profits?)|risk[- ]free investment|double your money|\d+% (?:daily|weekly|monthly) (?:returns?|profit))\b/i, 3, 'It promises investment gains. Real investments do not arrive by message with a promise attached.'],
    ['payment', 'Request for money that cannot be pulled back', /\b(gift cards?|bitcoin|crypto(?:currency)?|wire transfer|wire (?:the |me )?money|send (?:me )?money|zelle|venmo|cash ?app|transfer (?:your |the )?(?:money|funds)|safe account)\b/i, 2, 'It asks for money by a method chosen because the payment cannot be reversed.'],
    ['threat', 'Threat', /\b(arrest(?:ed)?|warrant|account (?:will be |is )?(?:suspended|frozen|locked)|legal action|shut off|deport(?:ed|ation)?)\b/i, 2, 'It threatens you. A threat is there to make you act before you check.'],
    ['secrecy', 'Demand for secrecy', new RegExp("\\b(don" + A + "t tell|do not tell|keep (?:this|it) (?:a )?secret|between (?:you and me|us)|tell no one)\\b", 'i'), 2, 'It tells you to keep this secret. That is how a scammer keeps you away from people who would stop you.'],
    ['remote', 'Remote access request', /\b(anydesk|teamviewer|remote access|remote control|install (?:this |the |our )?(?:software|app|program)|download (?:this |the |our )?(?:app|software))\b/i, 2, 'It wants software on your computer. That hands a stranger the controls.'],
    ['authority', 'Impersonation of an organization', /\b(FBI|IRS|Social Security|Medicare|fraud department|police|government agent|bank security)\b/i, 1, 'It uses the name of an organization you trust. Anyone can type a name.'],
    ['relative', 'Family emergency story', new RegExp("\\b(hi (?:mom|dad|grandma|grandpa)|grandma|grandpa|grandmother|grandfather|your grandson|your granddaughter|new number|bail money|I(?:" + A + "m| am) in trouble)\\b", 'i'), 1, 'It claims to be family in trouble. That story is a script.'],
    ['prize', 'Prize or refund lure', new RegExp("\\b(you(?:" + A + "ve| have) won|claim your prize|processing fee|release (?:your |the )?(?:prize|refund)|unclaimed refund)\\b", 'i'), 1, 'It dangles a prize or a refund you never asked about.'],
    ['support', 'Tech support scare', /\b(computer (?:is|has been) (?:infected|hacked)|virus detected|security alert|tech(?:nical)? support)\b/i, 1, 'It says your computer has a problem. A stranger cannot know that.'],
    ['urgency', 'Pressure to act now', /\b(immediately|urgent|act now|within \d+ (?:minutes|hours)|last chance|right now|final (?:notice|reminder)|today)\b/i, 1, 'It pushes you to act now. The hurry is the trick.'],
    ['romance', 'Affection from a stranger', /\b(my love|sweetheart|soulmate|love you|our future together)\b/i, 1, 'It uses affection to lower your guard.']
  ];

  function assess(input) {
    var hits = [];
    rules.forEach(function (r) { if (r[2].test(input)) hits.push({ id: r[0], kind: r[1], weight: r[3], reason: r[4] }); });
    var hasLink = /\bhttps?:\/\/[^\s<>"']+|\bwww\.[^\s<>"']+|\b[a-z0-9-]+\.(?:com|net|org|info|xyz|top|co)\b/i.test(input);
    hits.sort(function (a, b) { return b.weight - a.weight; });
    var reasons = hits.slice(0, 3).map(function (h) { return h.reason; });
    if (hasLink && reasons.length < 3) reasons.push('It carries a link. A genuine sender does not need you to click one.');

    if (hits.length || hasLink) {
      return {
        level: 'scam',
        verdict: 'Treat this as a scam.',
        kind: hits.length ? hits[0].kind + '.' : 'Unexpected link.',
        bot: 'Presume a machine or a script. Messages like this go out in bulk to thousands of numbers.',
        reasons: reasons,
        steps: ['Do not click, reply or pay.', 'If it names someone you deal with, reach them through a number you already have.', 'Delete the message.']
      };
    }
    return {
      level: 'presumed_scam',
      verdict: 'Were you expecting this? If not, treat it as a scam and ignore it.',
      kind: 'Unverified message.',
      bot: 'Presume a machine or a script until the sender proves otherwise.',
      reasons: ['A message you were not expecting is almost always a scam.', 'A genuine sender will reach you again with a message that explains itself.'],
      steps: ['Do not reply.', 'If it names someone you deal with, reach them through a number you already have.', 'Otherwise ignore it.']
    };
  }
  return { assess: assess };
})();

(function () {
  var MAX = 6000;
  var EXAMPLES = {
    bank: 'Brian, this is your bank’s fraud department. We detected a $4,850 transfer. Click here immediately to stop it.',
    family: 'Grandma, it is me. I’m in trouble and I need bail money today. Please don’t tell Mom. Can you buy gift cards and send me the numbers? I will explain later.',
    bot: 'Hi, I am an automated assistant from Lakeside Pharmacy. Your prescription is ready for pickup. Reply STOP to end these messages.'
  };
  // The reviewed wording for the bank example, shown when the page first opens.
  var OPENING = {
    level: 'scam',
    verdict: 'This is a scam. Do not click.',
    kind: 'Bank impersonation.',
    bot: 'Almost certainly a machine. This text went to thousands of phones at once with only the first name changed. Your name and number came off a list.',
    reasons: [
      'It never names the bank. A real alert says who it is from. A bulk text cannot, because the sender has no idea where you bank.',
      'A real fraud alert asks you to reply YES or NO, or to call. It does not need you to click a link.',
      'The exact dollar figure and the word “immediately” are there to make you act before you think.'
    ],
    steps: ['Do not click and do not reply.', 'If you are worried, call the number on the back of your card.', 'Delete the text.']
  };

  var form = document.getElementById('check-form'), box = document.getElementById('message'),
      body = document.getElementById('result-body'), hint = document.getElementById('result-hint'),
      err = document.getElementById('error'), count = document.getElementById('count'),
      runBtn = document.getElementById('run');
  var busy = false, slowTimer = null;

  function el(tag, text, cls) { var n = document.createElement(tag); if (text != null) n.textContent = text; if (cls) n.className = cls; return n; }
  function line(label, text) { var p = el('p'); p.appendChild(el('b', label + ' ')); p.appendChild(document.createTextNode(text)); return p; }
  function list(items, cls, tag) { var l = el(tag, null, cls); items.forEach(function (t) { l.appendChild(el('li', t)); }); return l; }

  function render(r) {
    body.textContent = '';
    var lv = el('div', null, 'level'); lv.setAttribute('data-level', r.level);
    lv.appendChild(el('strong', r.verdict));
    body.appendChild(lv);
    var facts = el('div', null, 'facts-list');
    facts.appendChild(line('Kind:', r.kind));
    facts.appendChild(line('Bot or person:', r.bot));
    body.appendChild(facts);
    body.appendChild(el('h3', 'How I know'));
    body.appendChild(list(r.reasons, 'reasons', 'ul'));
    body.appendChild(el('h3', 'What to do'));
    body.appendChild(list(r.steps, 'steps', 'ol'));
  }

  function showWorking() {
    body.textContent = '';
    var w = el('div', null, 'working'); w.appendChild(el('i')); w.appendChild(el('span', 'Reading the message...'));
    body.appendChild(w);
    slowTimer = setTimeout(function () { w.lastChild.textContent = 'Still reading. The first check of the day can take up to a minute.'; }, 6000);
  }

  function setBusy(on) {
    busy = on; runBtn.disabled = on; runBtn.textContent = on ? 'Checking...' : 'Check message';
    if (!on && slowTimer) { clearTimeout(slowTimer); slowTimer = null; }
  }

  function updateCount() { count.textContent = box.value.length.toLocaleString('en-US') + ' / ' + MAX.toLocaleString('en-US'); }

  function check(isExample) {
    if (busy) return;
    var text = box.value.trim();
    err.hidden = true;
    if (!text) { err.textContent = 'Paste a message before checking it.'; err.hidden = false; return; }
    if (text.length > MAX) { err.textContent = 'Please check up to 6,000 characters at a time.'; err.hidden = false; return; }
    setBusy(true); showWorking();
    hint.textContent = isExample ? 'For a made-up example.' : 'For the message you pasted.';

    var done = function (result, quick) {
      setBusy(false); render(result);
      if (quick) hint.textContent = 'Quick check. The full check could not be reached just now, so this answer is the short version.';
    };
    fetch('/api/check', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message: text }) })
      .then(function (res) { return res.json().catch(function () { return { ok: false }; }); })
      .then(function (data) {
        if (data && data.ok && data.result) done(data.result, false);
        else done(HBotRules.assess(text), true);
      })
      .catch(function () { done(HBotRules.assess(text), true); });
  }

  form.addEventListener('submit', function (e) { e.preventDefault(); check(false); });
  document.getElementById('clear').addEventListener('click', function () {
    if (busy) return;
    box.value = ''; updateCount(); err.hidden = true; body.textContent = '';
    body.appendChild(el('p', 'Paste a message and click Check message. You get a verdict, the reasons, and what to do.', 'hint'));
    hint.textContent = 'Ready when you are.'; box.focus();
  });
  box.addEventListener('input', updateCount);
  Array.prototype.forEach.call(document.querySelectorAll('[data-example]'), function (b) {
    b.addEventListener('click', function () { if (busy) return; box.value = EXAMPLES[b.getAttribute('data-example')]; updateCount(); check(true); });
  });

  box.value = EXAMPLES.bank; updateCount(); render(OPENING);
})();
