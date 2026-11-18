# Architectural restyle

**Problem.** The owner didn't like the v1.1.0 look. It reads as a generic dashboard template, not
a considered product. The content and features are right; the visual language isn't.

**Who it's for.** Hiring reviewers forming a first impression; anyone opening the live link.

**Appetite.** Half a day.

**Sketch.** Keep the LeaseLens name, data, pages and features. Apply the visual language of an
architectural brief (provided by the owner):
- **Palette:** charcoal `#141413`, off-white `#EDEAE4`, bronze `#B8A27A`, surface `#1E1D1B`,
  muted `#A39E95`, hairline lines. One light "stone" section (`#EDEAE4` with charcoal text). Every
  text color at least 4.5:1 against its background, computed. No text under 14 px.
- **Type:** Marcellus for headings and figures; Jost 300 body at 18 px; Jost 500 uppercase
  letterspaced labels and buttons.
- **Buttons:** one style: transparent, 1 px bronze border, bronze uppercase text, fills bronze on
  hover. Plus a text link with a thin leading line. No solid buttons, no pills, no icons in buttons.
- **Welcome page:** a full-bleed photo hero with the only gradient (the overlay); a large serif
  intro; the four health figures with bronze rules and a one-time count-up; three alternating image
  rows (dashboard, ask, weekly summary); a stone section "How the AI is kept honest" with I, II,
  III; the five largest buildings as a quiet list; a footer.
- **Motion** (`motion`): hero image settles from 1.06 to 1 over 2.4 s, heading fades up, image rows
  reveal with a bottom-to-top clip, numbers count up once. Off under `prefers-reduced-motion`.
- **Photos:** free-licence (Unsplash) architecture images, self-hosted and credited.
- **Charts:** a series palette re-validated against the charcoal surface (dataviz validator).

**Out of scope.** Renaming the product, changing data, new features, a register-interest form, a
map, a light theme toggle.

**Risks.**
- Text at 14 px or more makes dense tables and chart axes wider: check at 375 px.
- Status verdicts still need color plus a word plus an icon, using muted tones that pass contrast.
- Photos: licence and file size. Use the Unsplash licence, resize, and keep the total under about
  1.5 MB.

**Go / no-go.** Lighthouse accessibility 100 on all four pages, no horizontal scroll at 375 px,
`make check` green, all existing behaviour tests pass with only label/style updates, and the
welcome page loads in under 2 s on the live link once the API is warm.
