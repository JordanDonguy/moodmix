# Sprint 12 — Mobile App (Capacitor)

**Goal:** Installable iOS + Android app with background audio and lock-screen controls.

**Depends on:** Sprint 9 (auth/likes are needed for cross-device sync to feel meaningful on mobile)

## Scope

### Wrapper
- `npx cap init`, add iOS + Android platforms
- Build pipeline: `npm run build && npx cap sync`
- App icon + splash screen generated from a single source

### Background audio
- iOS: `UIBackgroundModes: ["audio"]` in `Info.plist`, set `AVAudioSession` category to `playback`
- Android: Foreground Service holding a wake lock during playback
- Verify the existing `MediaSession` integration carries through to native lock-screen controls

### YouTube embed in WebView
- Inject JS to suppress `visibilitychange`-triggered pauses (the trick Brave Nightly uses)
- Test autoplay edge cases on both platforms

### Mobile-native UX (replaces the desktop-style navbar on small screens)

The web app's mobile UX inherits the desktop navbar pattern (avatar dropdown top-right, sliders at the top of the grid). That works for the PWA but feels web-y inside a native shell. Replace it with a thumb-friendly bottom navigation:

- **No top navbar** on mobile — full vertical real estate goes to the grid
- **Bottom of screen, top to bottom**:
  - Player bar (existing)
  - 4-button bottom nav: Home · Search · Library · Account
- **Home / Library** buttons are pure navigation — tapping highlights the active tab and routes accordingly
- **Search / Account** buttons toggle a half-screen panel that slides up *above* the player bar:
  - Search panel: AI search bar + mood/energy/instrumentation sliders + genre dropdown + vocal toggle
  - Account panel: same items as the desktop dropdown (toggles, theme, legal, sign out)
- Tapping the active button (Search/Account) again closes the panel — visual highlight makes the close affordance obvious
- Sliders in the bottom-anchored panel are easier to reach with the thumb than top-anchored sliders

Inspirations: Spotify, Apple Music, YouTube Music — all use bottom-anchored navigation with a player bar above it. We just add the slide-up panel layer for filters and account, since we don't have a separate "now playing" view.

### Distribution
- iOS: TestFlight only. App Store public submission is likely blocked by Apple's review policies — guideline 5.2.5 (rejects WebView wrappers that primarily surface third-party content) and 5.2.1 (third-party IP — YouTube background play is a Premium feature). Friends/testers can install via TestFlight; public listing isn't realistic until the content story changes (licensed mixes, our own audio CDN, etc.).
- Android: Google Play closed testing track first, then production. Play has no equivalent of 5.2.5 and is significantly more permissive about WebView wrappers and YouTube-adjacent apps. Risk is reactive: if YouTube files a complaint, the app can be pulled — but it ships in the meantime.

## Out of scope

- Push notifications
- Native UI components beyond what Capacitor provides by default
- Deep linking / app links (defer)

## Decisions to make during impl

- Capacitor plugin for audio session: existing community plugin or write a minimal Swift one
- How to handle YouTube iframe focus loss on background — JS injection might break in future YouTube updates; have a fallback plan
- iOS bundle ID + signing setup — needs a paid Apple Developer account ($99/yr)
- Whether the mobile-native UX (bottom nav + slide-up panels) should also apply to the **mobile web** view, or only to the Capacitor-wrapped native shell. Probably both — the bottom nav is genuinely better mobile UX regardless of native-vs-web. But shipping it for native first is a cleaner scope boundary.
- Slide-up panel mechanics: full-height vs ~50% vs natural-content-height? Probably natural-content-height (sliders + genre dropdown only need ~400px)

## Done when

- App installs on physical iOS + Android devices via TestFlight + Play closed testing
- Audio plays in background on both platforms
- Lock screen shows mix title + play/pause/skip controls
- Play Store closed testing live with at least 5 testers from outside the dev team
- Mobile UX uses the bottom-nav pattern (Home / Search / Library / Account); top navbar hidden on mobile breakpoints
- Search and Account panels slide up above the player bar, dismissible by re-tapping the active button
