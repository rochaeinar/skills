<!--
TEMPLATE · Third-party (open-source) licenses (English). Read references/app-integration.md first.
Final file: <app>/app/src/main/assets/legal/licenses_en.md.
- Source of truth: `web.py licenses <slug>` (content/licenses-inventory.md): every artifact on the
  RELEASE runtime classpath with the license declared in its POM. Add what Gradle does not see:
  local modules/AARs, fonts in res/font or assets (OFL…), icon sets, sounds, images, data files.
- Only what SHIPS in the app. Test and build tools (JUnit, Espresso, Robolectric, lint, KSP…) are not
  distributed: leave them out.
- Group Apache 2.0 components in one table (component · author). Every other license (MIT, BSD,
  ISC, OFL, EPL, MPL, CC-BY…) gets its own section with the component, version, copyright holder
  and the FULL license text (MIT/BSD/ISC require reproducing the copyright and permission notice;
  take it from the project's LICENSE file, not from memory). OFL fonts: name the font, the
  copyright line and link the OFL 1.1 text.
- A component with no license found, or a copyleft license (GPL/LGPL/AGPL), is reported to the
  user before publishing: it may be incompatible with the app's distribution.
- Replace every {{PLACEHOLDER}} and delete every comment.
-->
**{{APP}}** uses open-source components and resources from third parties. Thanks to their authors and communities.

© {{YEAR}} {{DEVELOPER}}

---

## Summary

| Component | License |
| --- | --- |
| {{N}} components (AndroidX, Kotlin, Google…) | Apache 2.0 |
| {{COMPONENT}} | {{LICENSE}} |

## Apache License 2.0

These components are distributed under the [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0):

| Component | Author |
| --- | --- |
| {{COMPONENT}} | {{AUTHOR}} |

The full license text is available at [apache.org/licenses/LICENSE-2.0](https://www.apache.org/licenses/LICENSE-2.0).

## {{OTHER_LICENSE}}

**{{COMPONENT}}** {{VERSION}} · {{COPYRIGHT_HOLDER}}

<!-- What it is used for, in a few words, if it helps. Then the license text: -->

```
{{FULL_LICENSE_TEXT}}
```

## Fonts

<!-- One line per font: **Name** · copyright · [SIL Open Font License 1.1](https://openfontlicense.org).
  Icon fonts and icon sets too (e.g. Material Symbols · Google · Apache 2.0, if not listed above). -->
