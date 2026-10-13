# Kjøkkentavla – designspesifikasjon (v5)

Kjøkkentavla er en håndtegnet familietavle for **Waveshare 7.3" 7-farge e-papir (7.3F)**, 800 × 480 piksler i liggende format.

- Prototype: `kjokkentavle-konsept.html` (én SVG tegnet med rough.js og skriften Kalam).
- Forhåndsvisning av panelet: `panel_kvantisering.py`.
- Referansebilder: `kjokkentavle-v5-host.png` og `kjokkentavle-v5-jul.png`.

## 1. Prinsipper

- **Lesbart fra andre siden av kjøkkenet.** All tekst er minst 22 px. Tidspunkt for siste oppdatering vises ikke.
- **Lite tekst.** Hendelser vises med korte titler på ett til to ord. Det som ikke får plass, telles som «+N» i stedet for å vises.
- Teksten er alltid svart på hvitt. Farger brukes bare på figurer, personmerker og markeringer.
- Tegningene har et fast felt som alltid er ledig.

## 2. Panel og rendering

| Punkt | Krav |
|---|---|
| Oppløsning | 800 × 480, liggende. Tegnes rett vei og roteres 180° først i sendesteget, fordi panelet er montert opp ned. |
| Palett (indeks) | 0 svart `#000000`, 1 hvit `#FFFFFF`, 2 grønn `#00FF00`, 3 blå `#0000FF`, 4 rød `#FF0000`, 5 gul `#FFFF00`, 6 oransje `#FF8000` |
| Farger | Bare de sju rene fargene. Ingen gråtoner, ingen gjennomsiktighet og ingen dithering. |
| Kvantisering | Piksler med lav metning (max−min < 60) blir svart hvis luminansen er under ca. 150, ellers hvit. Andre piksler blir nærmeste palettfarge. Dette hindrer fargede kanter rundt tekst. Se `panel_kvantisering.py`. |
| Streker | Minst 1,5 px. |
| rough.js | Fast seed som nullstilles for hver tegning, slik at bildet blir identisk ved samme data og panelet ikke får gjenskygge. |

## 3. Typografi (Kalam 400/700)

| Element | px | Vekt |
|---|---|---|
| Temperatur nå | 40 | 700 |
| Dato | 36 | 700 |
| Temperatur i værfeltene | 30 | 700 |
| Nedtelling («19 dager») | 34 | 700 |
| Seksjonstittel («I morgen») | 28 | 700 |
| Hendelsestittel | 29 | 400 |
| Klokkeslett og ukedag | 26 | 700 |
| «Været i morgen» | 24 | 700 |
| Etiketter (klokkeslett i værfeltene, vind, nedbør, «til Halloween», «+N til») | 22 | 400 / 700 |
| Bokstav i personmerke | 21 | 700 |

Tekst brytes aldri over flere linjer. Den kortes med «…» hvis den likevel blir for lang.

## 4. Oppsett

```
┌──────────────────────────────────────────────────────────┐
│ Mandag 12. oktober ★                              ☾ 6°    │  hode y 14–74
├────────────────────────────────┬─────────────────────────┤
│ 08:30  Barnehagen              │ Været i morgen           │
│ 17:00 (E) Fotball              │  08    12    16    20    │
│ I morgen 🗑             +1 til │  ☁     ☁     ☁     🌧     │
│ 18:30 (K) Øvelseskjøring       │  6°    7°    8°    8°    │
│ 19:00 (S) Piano                │ ≋2    ≋4    ≋5    ≋3     │
│ 19:00  Foreldremøte            │                   💧2    │
│ - - - - - - - - - - - - - - -  │ - - - - - - - - - - - -  │
│ ons  Tannlege                  │ 🎃 19 dager              │
│ tor  Mariana               +2  │    til Halloween         │
│ fre  Lunsj                     │   sesongscene            │
└────────────────────────────────┴─────────────────────────┘
   venstre x 26–496              skillestrek x≈510   høyre x 522–776
```

### 4.1 Ramme og hode
- **Ramme: håndtegnet `~.~.~.~`** langs alle fire kanter, fra (11,11) til (789,469). Hver kant deles i like lange enheter på ca. 34 px. Hver enhet er en liten bølge (to kvadratiske kurver med utslag ±6 px, strek 2,2) fulgt av en fylt prikk (diameter 5,5). Antall enheter rundes slik at mønsteret går opp på hver kant. Se `waveBorder()` i prototypen.
- Datoen står til venstre (36 px, grunnlinje y=54). **Hele dagen-ikoner for i dag** står rett etter datoen.
- Til høyre står været nå: ikon (skala 1,2) og temperatur (40 px), høyrejustert mot x=772.
- Håndtegnet strek på y≈73.

### 4.2 Venstre kolonne: agenda
Radhøyden er 34 px.

1. **Dagens hendelser** starter rett under hodet (y=108) **uten tittel**, fordi det er gitt at de gjelder i dag. Maks 3.
2. **I morgen.** Tittel (28, fet) med eventuelle hele dagen-ikoner etter. Maks **3** hendelser. Flere enn tre gir «+N til», høyrejustert på tittellinjen.
3. Stiplet håndtegnet skillestrek.
4. **Senere.** Maks **3 dager**, én linje per dag: ukedag (25, fet) + første hendelse (28). Flere hendelser gir «+N» høyrejustert. Dager som ikke får plass før y≈452, utelates.

**Hendelsesrad:** `HH:MM` (fet) → personmerker → kort tittel. Bare starttid vises.

**Hele dagen-hendelser** (søppeltømming, reiser, merkedager) får ingen egen rad. De vises som ikon: for i dag etter datoen i hodet, for i morgen etter «I morgen».

**Personmerker:** håndtegnet sirkel (diameter 29, strek 3,2) i personens farge, med svart forbokstav inni. Flere personer står ved siden av hverandre med 31 px mellomrom.
- Farger: K rød, S blå, R grønn, E oransje, M gul.
- Prefiks som «K:» eller «S:» i kalenderteksten fjernes og vises som merke i stedet.

### 4.3 Høyre kolonne: været i morgen
- Tittelen «Været i morgen» (24, fet) står på y=108.
- **Fire like brede felt** (ca. 63 px): kl. **08, 12, 16 og 20**. Hvert felt har:
  - klokkeslett (22, fet) på y=138
  - ikon (skala 1,15)
  - temperatur (30, fet) på y=208
  - vind: lite vind-ikon + m/s som tall (22) på y=238
  - nedbør: blå dråpe + mm (22, fet, blå) på y=264, bare når det er nedbør. Avrundes til hele mm, og under 1 mm vises som «<1».
- Ingen enheter i teksten, fordi ikonene forteller om det er vind eller nedbør.
- Stiplet skillestrek på y≈276.

### 4.4 Sesongfelt (x 530–776, y 290–462)
- **Nedtelling:** ikon + «NN dager» (34, fet) og under det «til <høytid>» (22).
- **Scene:** sesongfigurer på en håndtegnet bakkelinje på y≈452, med noen få dekorfigurer i luften. Figurene må ikke overlappe teksten.

## 5. Korte titler

Kalendertitler gjøres om til korte titler på ett til to ord og maks ca. 16 tegn. Bredden på venstre kolonne gir plass til omtrent 15–16 tegn etter klokkeslett og merke.

Foreslått rekkefølge:
1. Bruk et eget felt for kort tittel hvis kalenderen har det, eller en ordliste/overstyring (`"Levere i barnehagen" → "Barnehagen"`).
2. Fjern personprefiks (`K:`, `S:`) og gjør dem om til merker.
3. Kutt etter « – », « - », « med », « hos », « i », « på », for eksempel «Øvelseskjøring med Solveig» → «Øvelseskjøring».
4. Kutt ved ordgrense til det passer. Bruk «…» bare som siste utvei.

## 6. Ikoner og figurer

Alle ikoner og figurer tegnes med rough.js: svart kontur og helfylt i en ren palettfarge.
- **Vær:** sky, regn, snø, måne, sol.
- **Hele dagen:** søppelbøtte, stjerne, fly, tann.
- **Høst:** blader, fluesopp, gresskar, eple, gress.
- **Jul:** grantre, gaver, snøfnugg, stjerne.

## 7. Sesongtema

```js
const THEME = {
  match(date) { /* true når temaet gjelder */ },
  countdown: { label: 'til Halloween', date: '10-31', icon: 'pumpkin' },
  vignette(x, y, w) { /* tegner scenen i sesongfeltet */ }
};
```

Forslag til temaer: høst, Halloween, advent/jul, vinter, påske, 17. mai, sommer. Nedtellingen viser nærmeste kommende høytid.

## 8. Datamodell (eksempel)

```js
{
  date: 'Mandag 12. oktober',
  now: { icon: 'moon', temp: '6°' },
  todayIcons: [],                      // hele dagen-ikoner, vises etter datoen
  today: [ { t: '08:30', title: 'Barnehagen' }, { t: '17:00', who: 'E', title: 'Fotball' } ],
  tomIcons: ['bin'],
  tomEv: [ { t: '18:30', who: 'K', title: 'Øvelseskjøring' }, /* … */ ],
  later: [ { dn: 'ons', ev: ['Tannlege'] }, { dn: 'tor', ev: ['Mariana', 'Høsttreff', 'Middag'] } ],
  wx: [ { k: '08', i: 'cloud', t: '6°', w: 2 }, { k: '12', i: 'cloud', t: '7°', w: 4 },
        { k: '16', i: 'cloud', t: '8°', w: 5 }, { k: '20', i: 'rain', t: '8°', w: 3, mm: '2' } ]
}
```

## 9. Testsjekkliste
- Se på panelsimuleringen fra 2–3 meters avstand. All tekst skal være lesbar.
- Test med 5 eller flere hendelser i morgen (skal gi «+N til»), lange titler, to–tre personmerker på én hendelse, −10° og en dag uten nedbør.
- Kontroller at ingenting går forbi y≈462 nederst.
- To gjengivelser med samme data skal gi piksel-identiske bilder.
- Rotasjonen på 180° skjer bare i sendesteget.
