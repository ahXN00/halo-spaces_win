Notes for the reviewer

halo.spaces is a design add-on (theme + icons + behaviour). It uses one Experiment API, "mailCards" (extension/api/implementation.js), because most of what it does is not possible with WebExtension APIs:

- applies the bundled stylesheet (extension/theme.css) to Thunderbird windows as a user sheet; small global sheets via nsIStyleSheetService: noscroll.css, icon-vars.css, plaintext.css (user sheets) and parts.css (author sheet, only ::part rules – ::part does not apply from user sheets)
- reshapes the message list into cards (avatar, preview) and optional hover actions (off by default): flag/archive/delete via folder.markMessagesFlagged / MessageArchiver / folder.deleteMessages, on the hovered message only
- message header: sender picture, folder name next to the date; for mailing lists a note with an "Unsubscribe" button that only on click opens the List-Unsubscribe https link in the default browser (or a prefilled compose window for mailto – never sent automatically)
- spaces toggle, Today pane toggle, an agenda card and a quick event/task window (creates events only through the calendar API when the user confirms)
- a read-only "Birthdays" memory calendar built from address book cards (bday)
- sender logos: DNS TXT lookup for BIMI (resource:///modules/DNS.sys.mjs) and HTTPS fetches to the sender's own domain only; can be turned off in the add-on's preferences; reserved TLDs and non-public hosts are blocked (isPublicHttps)
- update check at start (AddonManager findUpdates, at most every 6 hours, respects AddonManager.updateEnabled and the add-on's applyBackgroundUpdates; can be turned off)

Everything is removed again on disable/uninstall (restorers in implementation.js, onShutdown).

No code is minified, obfuscated or loaded remotely. No eval/new Function. innerHTML is used once, for a static, built-in SVG icon string (replaced by DOMParser in the next version).

Build instructions (source code upload):
1. Requirements: macOS or Linux with zsh, python3 (3.9+) and zip – no other tools, no npm.
2. Unpack the source archive and run:  ./build.sh
3. Result: dist/halo-spaces-<version>-atn.xpi is the submitted package (dist/halo-spaces-<version>.xpi is the self-hosted GitHub variant).
The only generated file is extension/theme.css: chrome/merge_spaces.py inserts chrome/spaces.css into chrome/userChrome.css, which build.sh copies to extension/theme.css. For the store package build.sh removes update_url from the manifest and adds strict_max_version from store/max-version.

Test: install, choose "System theme – auto" under Themes, restart Thunderbird once. An automated test runs in a fresh temporary profile: python3 tests/halo_test.py
