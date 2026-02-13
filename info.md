# Tandem Source / Carelink Integration - Home Assistant

Custom component for Home Assistant to monitor **Tandem t:slim insulin pumps** via [Tandem Source](https://source.tandemdiabetes.com) and **Medtronic pumps** via the [Carelink platform](https://carelink.minimed.eu).

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

## Supported devices

### Tandem
- Tandem t:slim X2 pump with Control-IQ technology
- Compatible with Tandem Source (EU and US regions)

### Medtronic
- Medtronic MiniMed 780G pump
- Medtronic MiniMed 770G pump (*to be confirmed*)
- Medtronic Guardian Connect CGM (*to be confirmed*)

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
