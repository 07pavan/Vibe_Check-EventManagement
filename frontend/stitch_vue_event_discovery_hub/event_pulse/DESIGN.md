---
name: Event Pulse
colors:
  surface: '#fef7ff'
  surface-dim: '#dfd7e6'
  surface-bright: '#fef7ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f9f1ff'
  surface-container: '#f3ebfa'
  surface-container-high: '#ede5f4'
  surface-container-highest: '#e8dfee'
  on-surface: '#1d1a24'
  on-surface-variant: '#4a4455'
  inverse-surface: '#332f39'
  inverse-on-surface: '#f6eefc'
  outline: '#7b7487'
  outline-variant: '#ccc3d8'
  surface-tint: '#732ee4'
  primary: '#630ed4'
  on-primary: '#ffffff'
  primary-container: '#7c3aed'
  on-primary-container: '#ede0ff'
  inverse-primary: '#d2bbff'
  secondary: '#00687a'
  on-secondary: '#ffffff'
  secondary-container: '#57dffe'
  on-secondary-container: '#006172'
  tertiary: '#7d3d00'
  on-tertiary: '#ffffff'
  tertiary-container: '#a15100'
  on-tertiary-container: '#ffe0cd'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#eaddff'
  primary-fixed-dim: '#d2bbff'
  on-primary-fixed: '#25005a'
  on-primary-fixed-variant: '#5a00c6'
  secondary-fixed: '#acedff'
  secondary-fixed-dim: '#4cd7f6'
  on-secondary-fixed: '#001f26'
  on-secondary-fixed-variant: '#004e5c'
  tertiary-fixed: '#ffdcc6'
  tertiary-fixed-dim: '#ffb784'
  on-tertiary-fixed: '#301400'
  on-tertiary-fixed-variant: '#713700'
  background: '#fef7ff'
  on-background: '#1d1a24'
  surface-variant: '#e8dfee'
typography:
  display-xl:
    fontFamily: Inter
    fontSize: 48px
    fontWeight: '800'
    lineHeight: '1.1'
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '700'
    lineHeight: '1.2'
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '700'
    lineHeight: '1.3'
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: '1.6'
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.5'
  label-caps:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: '1.0'
    letterSpacing: 0.05em
rounded:
  sm: 0.5rem
  DEFAULT: 1rem
  md: 1.5rem
  lg: 2rem
  xl: 3rem
  full: 9999px
spacing:
  base: 4px
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 48px
  gutter: 16px
  margin-mobile: 20px
---

## Brand & Style

The design system is engineered to capture the kinetic energy of live experiences. It targets a demographic that values spontaneity, social connection, and ease of discovery. The aesthetic is a fusion of **Modern Minimalism** and **High-Contrast Boldness**, ensuring that while the interface remains clean and unobtrusive, the call-to-action elements and event imagery vibrate with intensity.

By leveraging a mobile-first philosophy, this design system prioritizes thumb-friendly interactions and rapid scannability. The emotional goal is to evoke excitement and "FOMO" (fear of missing out) through vibrant accents, while maintaining a sense of premium reliability through sophisticated typography and generous whitespace.

## Colors

The palette is anchored by **Electric Violet**, a color that symbolizes creativity and nighttime energy. This primary hue is used for critical action points and active states. The background utilizes a **Soft Gray** (Slate 50) to reduce eye strain and provide a neutral canvas that allows colorful event photography to pop.

High-contrast text tokens (Slate 900) ensure the design system meets WCAG AA accessibility standards, providing legibility even in outdoor, high-glare environments. Secondary accents like Neon Cyan and Rose are reserved for category tagging and status indicators (e.g., "Selling Out Fast").

## Typography

The design system utilizes **Inter** exclusively to maintain a clean, systematic appearance. The type hierarchy relies on extreme weight variance—using Extra Bold (800) for headers to create a sense of urgency and Regular (400) for body copy to ensure readability.

The "label-caps" style is specifically designed for metadata such as dates, times, and venue names, providing a clear visual distinction from descriptive content. Tight letter-spacing on larger headings reinforces the modern, sleek aesthetic.

## Layout & Spacing

This design system employs a **fluid grid** optimized for mobile viewports. It uses a 4-column structure for handheld devices, expanding to a 12-column layout for desktop environments. The rhythm is based on a 4px baseline grid, ensuring consistent vertical alignment.

Padding within components is generous to facilitate ease of touch. Margins are set at 20px on mobile to prevent content from crowding the edges of modern edge-to-edge displays.

## Elevation & Depth

To create a sense of hierarchy on the soft gray background, the design system uses **Ambient Shadows**. These are extra-diffused and low-opacity, using a subtle tint of the primary violet color (#7C3AED) rather than pure black to maintain a "high-energy" and clean feel.

- **Level 1 (Cards):** Light shadow with an 8px blur, used for event cards to make them feel interactable.
- **Level 2 (Modals/Pickers):** Deeper shadow with a 24px blur, used for floating action sheets.
- **Interactive State:** Elements should "lift" on hover or press, increasing shadow spread to simulate physical proximity to the user.

## Shapes

The shape language is dominated by **full-radius curves**. This design system prioritizes "Pill-shaped" elements for buttons and tags to convey a friendly, organic, and modern energy. 

- **Pill-shaped (999px):** All buttons, input fields, and category chips.
- **Rounded-XL (24px):** Primary event cards and image containers.
- **Rounded-LG (16px):** Nested containers and secondary UI blocks.

## Components

### Buttons
Primary buttons are strictly pill-shaped with a solid Electric Violet fill and white text. Secondary buttons should use a "ghost" style—thick 2px borders with high-contrast text to maintain visibility without competing with the primary CTA.

### Cards
Event cards are the centerpiece of the design system. They feature a 2:3 or 16:9 aspect ratio image at the top with a "Rounded-XL" corner radius. The content area below uses high-contrast text for the event title and "label-caps" for the date and location.

### Chips & Tags
Used for music genres or event types. These are small pill-shaped elements with semi-transparent fills (10% opacity of the primary color) to provide visual categorization without cluttering the screen.

### Inputs
Search bars and text fields follow the pill-shaped theme. On focus, the border should transition to Electric Violet with a soft outer glow (bloom effect) to signal activity.

### Navigation
A "Floating Bottom Dock" is recommended for mobile, using a glassmorphic background (background blur: 12px) to allow content to scroll underneath while keeping navigation accessible.