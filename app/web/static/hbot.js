/* H-BOTdetector rule screening, version 1. Same rules as the first prototype. Runs in this page only. */
var HBot = (function () {
  var A = "[’']";
  var rules = [
    ['urgency', 'Pressure to act quickly', /\b(immediately|urgent|act now|within \d+ (?:minutes|hours)|last chance|right now)\b/i, 1, 'Pressure can make it harder to check a story.'],
    ['authority', 'Claimed authority', /\b(FBI|IRS|Social Security|Medicare|fraud department|police|government agent|bank security)\b/i, 1, 'A familiar organization’s name does not establish who sent this.'],
    ['threat', 'Threat or frightening consequence', /\b(arrest(?:ed)?|warrant|account (?:will be |is )?(?:suspended|frozen|locked)|legal action|shut off|deport(?:ed|ation)?)\b/i, 2, 'Threats can be used to push you into acting before verifying.'],
    ['secrecy', 'Request for secrecy', new RegExp("\\b(don" + A + "t tell|do not tell|keep (?:this|it) (?:a )?secret|between (?:you and me|us)|tell no one)\\b", 'i'), 2, 'Keeping you away from people you trust is a manipulation tactic.'],
    ['payment', 'Sensitive payment method', /\b(gift cards?|bitcoin|crypto(?:currency)?|wire transfer|wire (?:the |me )?money|send (?:me )?money|transfer (?:your |the )?(?:money|funds)|safe account)\b/i, 2, 'An unexpected payment request needs independent verification.'],
    ['credentials', 'Request for private account information', /\b(?:send|share|give|provide|enter|confirm|verify|tell)\b[\s\S]{0,70}\b(?:password|PIN|verification code|one[- ]time (?:code|password)|OTP|social security number|bank details|card number|seed phrase)\b/i, 3, 'Do not give private credentials or sign-in codes to an unsolicited contact.'],
    ['remote', 'Remote access or software request', /\b(anydesk|teamviewer|remote access|remote control|install (?:this |the |our )?(?:software|app|program)|download (?:this |the |our )?(?:app|software))\b/i, 2, 'Remote access can let someone control your device and accounts.'],
    ['support', 'Computer infection claim', /\b(computer (?:is|has been) (?:infected|hacked)|virus detected|security alert|tech(?:nical)? support)\b/i, 1, 'Unexpected technical warnings deserve a check through a source you already trust.'],
    ['investment', 'Promised investment returns', /\b(guaranteed (?:returns?|profits?)|risk[- ]free investment|double your money|\d+% (?:daily|weekly|monthly) (?:returns?|profit))\b/i, 3, 'Promises of exceptional or guaranteed investment gains are a warning sign.'],
    ['prize', 'Prize or refund lure', new RegExp("\\b(you(?:" + A + "ve| have) won|claim your prize|processing fee|release (?:your |the )?(?:prize|refund)|unclaimed refund)\\b", 'i'), 1, 'A promised reward can be a lure for money or personal information.'],
    ['relative', 'Family emergency claim', new RegExp("\\b(grandma|grandpa|grandmother|grandfather|your grandson|your granddaughter|bail money|I(?:" + A + "m| am) in trouble)\\b", 'i'), 1, 'Verify an unexpected family emergency through a known contact.'],
    ['romance', 'Emotional relationship language', /\b(my love|sweetheart|soulmate|love you|our future together)\b/i, 1, 'Affection is not suspicious by itself. A financial request changes the context.']
  ];
  function analyze(input) {
    if (typeof input !== 'string' || !input.trim()) throw new Error('Paste a message before checking it.');
    if (input.length > 20000) throw new Error('Please check up to 20,000 characters at a time.');
    var findings = [];
    rules.forEach(function (r) {
      var m = input.match(r[2]);
      if (m) findings.push({ id: r[0], title: r[1], evidence: m[0], weight: r[3], reason: r[4] });
    });
    var found = input.match(/\bhttps?:\/\/[^\s<>"']+|\bwww\.[^\s<>"']+/gi) || [];
    var urls = found.filter(function (u, i) { return found.indexOf(u) === i; });
    if (urls.length) findings.push({ id: 'link', title: 'Link included', evidence: urls[0], weight: 1, reason: 'This tool does not visit links or verify where they lead.' });
    for (var i = 0; i < urls.length; i++) {
      try {
        var u = new URL(urls[i].indexOf('www.') === 0 ? 'https://' + urls[i] : urls[i]);
        if (u.username || /^\d{1,3}(?:\.\d{1,3}){3}$/.test(u.hostname) || u.hostname.indexOf('xn--') !== -1 || /^(bit\.ly|tinyurl\.com|t\.co|is\.gd|rb\.gy)$/.test(u.hostname)) {
          findings.push({ id: 'unusual_link', title: 'Link needs extra care', evidence: urls[i], weight: 2, reason: 'This address is shortened, encoded, or uses a bare number. That does not prove fraud.' });
          break;
        }
      } catch (e) { /* leave malformed addresses as plain links */ }
    }
    var ids = {};
    findings.forEach(function (f) { ids[f.id] = true; });
    var points = findings.reduce(function (n, f) { return n + f.weight; }, 0);
    var serious = (ids.credentials && (ids.authority || ids.link || ids.urgency)) || (ids.payment && (ids.secrecy || ids.threat || ids.investment)) || (ids.remote && ids.support);
    if (serious) points = Math.max(points, 7);
    var level = points >= 7 ? 'high' : points >= 3 ? 'caution' : 'limited';
    var disclosed = input.match(new RegExp("\\b(I(?:" + A + "m| am) (?:an? |your )?(?:AI|automated|chatbot|bot)|automated (?:assistant|message|system)|AI assistant|chatbot)\\b", 'i'));
    var next = level === 'high'
      ? ['Pause before replying, paying, clicking, or installing anything.', 'Verify the story using a phone number or website you already know.', 'Ask someone you trust to review the message with you.']
      : level === 'caution'
        ? ['Check the sender through a known, independent contact.', 'Do not share passwords, sign-in codes, or payment details.']
        : ['If the request is unexpected, verify who sent it before acting.'];
    if (ids.relative) next.push('Call your relative using their usual number.');
    if (ids.authority) next.push('Contact the organization through its official app or a number from your own records.');
    return { level: level, findings: findings, next: next, disclosed: disclosed ? disclosed[0] : null };
  }
  return { analyze: analyze };
})();

(function () {
  var EXAMPLES = {
    bank: 'This is the fraud department at your bank. We detected a $4,850 transfer. Your account will be frozen unless you act immediately. Verify your password and verification code here: https://bank-security.example/verify',
    family: 'Grandma, it is me. I’m in trouble and I need bail money today. Please don’t tell Mom. Can you buy gift cards and send me the numbers? I will explain later.',
    bot: 'Hi, I am an automated assistant from Lakeside Pharmacy. Your prescription is ready for pickup. Reply STOP to end these messages.'
  };
  var LEVELS = {
    high: ['Many warning signs', 'Pause and verify before you do anything.'],
    caution: ['Some warning signs', 'Check who sent this before you act.'],
    limited: ['Few or no warning signs matched', 'This does not establish that the message is safe.']
  };
  var box = document.getElementById('message'), body = document.getElementById('result-body'),
      hint = document.getElementById('result-hint'), err = document.getElementById('error'),
      count = document.getElementById('count');

  function el(tag, text, cls) { var n = document.createElement(tag); if (text != null) n.textContent = text; if (cls) n.className = cls; return n; }

  function render(r) {
    body.textContent = '';
    var lv = el('div', null, 'level'); lv.setAttribute('data-level', r.level);
    lv.appendChild(el('strong', LEVELS[r.level][0])); lv.appendChild(el('span', LEVELS[r.level][1]));
    body.appendChild(lv);
    var who = el('p', null, 'who'); who.appendChild(el('b', 'Bot or person? '));
    who.appendChild(document.createTextNode(r.disclosed ? 'The message says it is automated ("' + r.disclosed + '"). Who sent it is still unverified.' : 'Cannot tell from the text alone.'));
    body.appendChild(who);
    body.appendChild(el('h3', 'What stood out'));
    if (r.findings.length) {
      var ul = el('ul', null, 'findings');
      r.findings.forEach(function (f) {
        var li = el('li'); li.appendChild(el('b', f.title)); li.appendChild(el('q', f.evidence)); li.appendChild(el('p', f.reason)); ul.appendChild(li);
      });
      body.appendChild(ul);
    } else {
      body.appendChild(el('p', 'No warning phrases matched. A deceptive sender can still write an ordinary-looking message.', 'hint'));
    }
    body.appendChild(el('h3', 'What to do next'));
    var nx = el('ul', null, 'next'); r.next.forEach(function (t) { nx.appendChild(el('li', t)); }); body.appendChild(nx);
    body.appendChild(el('p', 'Rule screening, version 1. The result describes matched warning signs. It is not a probability of fraud.', 'method'));
  }
  function updateCount() { count.textContent = box.value.length.toLocaleString('en-US') + ' / 20,000'; }
  function run(isExample) {
    err.hidden = true;
    try { render(HBot.analyze(box.value)); hint.textContent = isExample ? 'Shown for a made-up example. Paste your own message to replace it.' : 'For the message you pasted.'; }
    catch (e) { err.textContent = e.message; err.hidden = false; }
  }
  document.getElementById('check-form').addEventListener('submit', function (e) { e.preventDefault(); run(false); });
  document.getElementById('clear').addEventListener('click', function () {
    box.value = ''; updateCount(); err.hidden = true; body.textContent = '';
    body.appendChild(el('p', 'Paste a message and click Check message. The warning signs, the words that triggered them, and next steps appear here.', 'hint'));
    hint.textContent = 'Ready when you are.'; box.focus();
  });
  box.addEventListener('input', updateCount);
  Array.prototype.forEach.call(document.querySelectorAll('[data-example]'), function (b) {
    b.addEventListener('click', function () { box.value = EXAMPLES[b.getAttribute('data-example')]; updateCount(); run(true); });
  });
  box.value = EXAMPLES.bank; updateCount(); run(true);
  hint.textContent = 'Shown for the made-up bank example. Paste your own message to replace it.';
})();
