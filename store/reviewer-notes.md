Notes for the reviewer

halo.spaces is a design add-on (theme + icons + behaviour). It uses one Experiment API, "mailCards" (extension/api/implementation.js), because most of what it does is not possible with WebExtension APIs:

- applies the bundled stylesheet (extension/theme.css) to Thunderbird windows as a user sheet, plus two small global sheets (noscroll.css, icon-vars.css) via nsIStyleSheetService
- reshapes the message list into cards (avatar, preview) and optional hover actions (off by default) (flag/archive/delete using folder.markMessagesFlagged / MessageArchiver / folder.deleteMessages on the hovered message only)
- adds the spaces toggle, the Today pane toggle, an agenda card and a quick event/task window (creates events only through cal.manager / calendar.addItem when the user confirms)
- a read-only "Birthdays" memory calendar built from address book cards (bday)
- sender logos: DNS TXT lookup for BIMI (resource:///modules/DNS.sys.mjs) and HTTPS fetches to the sender domain only; can be turned off in the add-on's preferences; reserved TLDs and non-public hosts are blocked (isPublicHttps)

Everything is removed again on disable/uninstall (restorers in implementation.js, onShutdown).

No code is minified, generated or loaded remotely. The only generated file is extension/theme.css, a copy of chrome/userChrome.css (with chrome/spaces.css merged in) – see build.sh in the repository: https://github.com/sruf79/halo-spaces

No eval/new Function. innerHTML is used once, for a static, built-in SVG icon string.

Test: install, choose "System theme – auto", restart. An automated test runs in a fresh temporary profile: tests/halo_test.py in the repository.
