// Geschwindigkeitsmessung für tests/halo_test.py --perf (Chrome-Kontext, PRELUDE-Hilfen)
const N = 5000;
const { MailServices } = ChromeUtils.importESModule("resource:///modules/MailServices.sys.mjs");
const { AddonManager } = ChromeUtils.importESModule("resource://gre/modules/AddonManager.sys.mjs");
try { MailServices.accounts.localFoldersServer; } catch { MailServices.accounts.createLocalMailAccount(); await wait(500); }
const root = MailServices.accounts.localFoldersServer.rootFolder;
if (!root.containsChildNamed("Perf")) { root.createSubfolder("Perf", null); await wait(800); }
const folder = root.getChildNamed("Perf");
if (folder.getTotalMessages(false) < N) {
  const names = ["Anna Berger", "Newsletter", "GitHub", "Ben Huber", "Team", "Shop", "Clara Wolf", "Support"];
  const msgs = [];
  for (let i = 0; i < N; i++) {
    const n = names[i % names.length], day = 1 + (i % 28), min = String(i % 60).padStart(2, "0");
    msgs.push(`From - Sat Oct 17 10:00:00 2026\r\nFrom: ${n} <user${i % 300}@host${i % 40}.example.invalid>\r\nSubject: Betreff Nummer ${i} mit etwas mehr Text\r\nDate: ${day} Sep 2026 10:${min}:00 +0200\r\nMessage-ID: <perf-${i}@example.invalid>\r\nContent-Type: text/plain; charset=UTF-8\r\n\r\nHallo,\r\ndas ist die Vorschau von Nachricht ${i}. Noch eine Zeile Text, damit die Vorschau zwei Zeilen füllt.\r\n`);
  }
  folder.QueryInterface(Ci.nsIMsgLocalMailFolder).addMessageBatch(msgs);
  await wait(3000);
}
const frame = () => new Promise(r => w.requestAnimationFrame(r));
const measure = async () => {
  const a3 = await toMail();
  a3.displayFolder(root.getChildNamed("Inbox")?.URI || root.URI); await wait(800);
  // Ordner öffnen bis die ersten Zeilen stehen
  let t0 = performance.now();
  a3.displayFolder(folder.URI);
  const tree = a3.document.getElementById("threadTree");
  for (let i = 0; i < 300 && tree.querySelectorAll("tbody tr").length < 5; i++) await frame();
  await frame();
  const open = performance.now() - t0;
  // scrollen: 120 Bilder lang je 400 px, Dauer je Bild messen
  // scrollToIndex statt scrollTop: Thunderbird stellt die Liste beim Öffnen
  // sonst gern wieder auf die zuletzt gezeigte Zeile zurück
  tree.scrollToIndex(0); await wait(300);
  const sc = tree.scrollable || tree;
  const times = []; let last = performance.now();
  for (let i = 0; i < 120; i++) { tree.scrollToIndex(Math.min(40 * (i + 1), N - 1)); await frame(); const now = performance.now(); times.push(now - last); last = now; }
  times.sort((x, y) => x - y);
  // Kalender-Monatsansicht aufbauen
  t0 = performance.now(); await toCalendar(); w.switchToView("month"); await frame(); await frame();
  const calendar = performance.now() - t0 - 1500; // toCalendar wartet fest 1,5 s
  return { rows: a3.gDBView?.rowCount, open: Math.round(open), frameMedian: +times[60].toFixed(1), frameP95: +times[113].toFixed(1), frameMax: +times[119].toFixed(1), scrolled: Math.round(sc.scrollTop), calendar: Math.round(calendar) };
};
const withHalo = await measure();
await measure(); const withHalo2 = await measure(); // zweite Runde: warm
const addon = await AddonManager.getAddonByID("mail-cards@sebastian.local");
await addon.disable(); await wait(3000);
await measure(); const without = await measure();
return { withHalo, withHalo2, without };
