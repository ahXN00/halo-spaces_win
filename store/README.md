# Store listing (addons.thunderbird.net)

Everything needed for the listing on addons.thunderbird.net (ATN). Texts are
ready to paste; the package is `dist/halo-spaces-<version>-atn.xpi`
(built by `./build.sh`, identical to the GitHub package except that it has no
`update_url` – ATN delivers updates itself).

| Field | Value |
|---|---|
| Name | halo.spaces |
| URL slug | `halo-spaces` |
| Summary | see `listing-en.md` / `listing-de.md` (first block, ≤ 250 characters) |
| Description | see `listing-en.md` / `listing-de.md` |
| Categories | Appearance · Calendar and Date/Time · Message and News Reading |
| Tags | design, macos, layout, calendar, contacts, today pane, dark mode |
| Support e-mail | (as in the add-on's feedback window) |
| Support site | https://github.com/sruf79/halo-spaces/issues |
| Homepage | https://github.com/sruf79/halo-spaces |
| License | Mozilla Public License 2.0 |
| Privacy policy | `privacy-en.md` (required: the add-on loads sender logos) |
| Notes to reviewer | `reviewer-notes.md` |
| Screenshots | `../screenshots/mail.png`, `calendar.png`, `addressbook.png`, `quick-event.png` (personal data blurred) |
| Icon | `../extension/about/icon.svg` (export as 128×128 PNG: `store/icon-128.png`) |

Later versions: `./publish.sh <version> notes.md` also uploads the store
package when `~/.config/halo-spaces/atn.env` exists (see `atn_upload.py`).
