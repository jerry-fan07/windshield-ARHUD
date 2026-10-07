<div align="center">

<h1>windshield-ARHUD</h1>

<p><b>An augmented-reality windshield heads-up display built on <a href="https://github.com/commaai/openpilot">openpilot</a>.</b></p>

</div>

## About

AR heads up display (HUD) that projects data onto the road and also uses OpenPilot’s self driving technology for adaptive cruise control and automated lane centering.
<!-- TODO: describe what the HUD shows (e.g. lane lines, lead car, speed) and the hardware it runs on. -->

## How it works

Uses a projection onto a relay mirror and a camera neural network on an NVIDIA Jetson attached to the car.
<!-- TODO: explain which openpilot data the HUD uses and how it gets drawn on the windshield. -->

## Getting started

```bash
git clone https://github.com/jerry-fan07/windshield-ARHUD.git
cd windshield-ARHUD
git lfs install
git submodule update --init --recursive
```

[Git LFS](https://git-lfs.com) is required: openpilot's models, fonts, and UI assets are stored with it.

## Built on openpilot

This project is based on [openpilot](https://github.com/commaai/openpilot) by [comma.ai](https://comma.ai). See the [openpilot README](/README.md) for openpilot's own documentation, supported cars, and setup instructions.

The `openpilot-base` branch tracks upstream openpilot unmodified; `main` contains this project's changes.

## Safety

**This is experimental research software, not a product.** Do not let it distract you from driving. You are responsible for complying with local laws and regulations. No warranty expressed or implied.

## License

openpilot is released under the [MIT License](/LICENSE), Copyright (c) 2018, Comma.ai, Inc. Some parts of the software are released under other licenses as specified.
