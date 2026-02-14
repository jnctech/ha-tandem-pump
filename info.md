# Tandem Source / Carelink Integration - Home Assistant

Custom component for Home Assistant to monitor **Tandem t:slim insulin pumps** via [Tandem Source](https://source.tandemdiabetes.com) and **Medtronic pumps** via the [Carelink platform](https://carelink.minimed.eu).

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

## Supported devices

### Tandem (tested)
- Tandem t:slim X2 pump with Control-IQ technology
- Compatible with Tandem Source (EU and US regions)

### Medtronic (inherited, not tested under this fork)
- Medtronic MiniMed 780G pump
- Medtronic MiniMed 770G pump
- Medtronic Guardian Connect CGM

> **Note:** Medtronic Carelink support was inherited from the [original integration](https://github.com/yo-han/Home-Assistant-Carelink) by @yo-han. It has **not been tested** under this fork. If you use Medtronic devices, please refer to the [original repo](https://github.com/yo-han/Home-Assistant-Carelink) for verified Carelink support, or open an issue if you'd like to help test.

## Features
- Real-time glucose monitoring (mg/dL and mmol/L)
- Insulin on board (IOB) tracking
- Basal rate monitoring
- Bolus and meal bolus history
- Historical data import between polls (state replay + long-term statistics)
- Optional Nightscout upload

## Credits
- Tandem Source integration by [@jnctech](https://github.com/jnctech)
- Original Carelink integration by [@yo-han](https://github.com/yo-han)
- Carelink API based on work by [@ondrej1024](https://github.com/ondrej1024)
- Binary event format reference from [tconnectsync](https://github.com/jwoglom/tconnectsync) by [@jwoglom](https://github.com/jwoglom)
