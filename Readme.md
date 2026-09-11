# mocopi Receiver Plugin for Blender

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](./LICENSE)

mocopi Receiver Plugin for Blender is a plugin for receiving motion data transmitted from the mocopi app and applying it to 3D avatars in Blender in real-time.

## License Notice
- This project is licensed under the Apache License 2.0 - see the [LICENSE](./LICENSE) file for details.
- Notwithstanding the foregoing, this repository does not include the mocopi logo or application icons. Use of these assets requires entering into a separate mocopi Logo and Icon License Agreement. ([here](https://www.sony.co.jp/en/Products/mocopi-dev/en/others/LogoGuideline.html))

## Overview

**mocopi** is a motion capture system that captures full-body motion data using a smartphone app or PC app combined with mocopi sensors. This extension allows you to seamlessly integrate mocopi motion tracking data with Blender's animation workflow.

## Features

- **Real-time Motion Capture**: Receive live motion data from mocopi devices via UDP
- **Automatic Bone Mapping**: Support for various armature bone naming conventions
- **Animation Recording**: Record and apply motion capture data to Blender armatures
- **Multiple Avatar Support**: Handle multiple mocopi receivers simultaneously

## System Requirements

- **Blender**: Version 4.2.0 or higher
- **Operating Systems**: Windows, macOS, Linux
- **Network**: UDP connection capability for mocopi communication
- **Hardware**: Compatible mocopi motion tracking system

## Installation

1. Download the latest release from the [Releases](https://github.com/sony/mocopi-receiver-plugin-blender/releases) page
2. In Blender, go to **Edit** > **Preferences** > **Add-ons**
3. Click **Install** and select the downloaded `.zip` file
4. Enable the **mocopi Receiver** add-on in the list

## Usage

### Basic Setup

1. Open Blender and import or create an armature
2. In the 3D Viewport, open the **N-panel** (press `N`)
3. Navigate to the **mocopi Receiver** tab

### Configuration

1. **Select Target Armature**: Choose the armature you want to animate
2. **Set Network Port**: Configure the UDP port for mocopi communication (default: 12351)
3. **Bone Mapping**: The add-on automatically detects and maps bones based on common naming conventions

### Recording Animation

1. Click **Connect** to establish connection with mocopi device
2. Ensure your mocopi system is broadcasting to the correct IP and port
3. Click **Start Recording** to begin capturing motion data
4. Perform your motion capture session
5. Click **Stop Recording** to finish and apply the animation

### Supported Bone Names

The add-on supports various armature naming conventions including:
- Standard Blender bone names
- Mixamo rigging
- VRM/VRoid bone structures
- Custom bone naming patterns

## Legacy vs. Generic Mode

Each mocopi receiver has a mode dropdown: **Legacy** or **Generic**, controlling how motion data is applied. In code this is referred to as V1 (legacy) and V2 (generic).

- **Legacy**: Writes motion directly to your armature as it arrives. Simplest and lowest-latency, but best for rigs already close to the mocopi skeleton's proportions/orientation. Recording starts as soon as you connect.
- **Generic**: Applies motion to a hidden reference skeleton, then retargets it onto your armature. Use **Start/Stop Recording** to capture. Motion is baked onto your armature after stopping. Handles proportion/naming differences better, so it suits custom, Mixamo, or VRM/VRoid rigs.

Start with **Generic** for most custom rigs.  Use **Legacy** for rigs that closely match the mocopi skeleton or for the simplest real-time path.

## Technical Details

### Network Protocol
- **Protocol**: UDP
- **Default Port**: 12351
- **Data Format**: Binary mocopi format with bone transformation data
- **Max Bones**: 27 bone tracking points

### Bone Mapping
The system automatically maps mocopi bone IDs to armature bones using predefined naming patterns:
- Root/Hip bones
- Spine/Torso segments (1-7)
- Neck and Head
- Arms and Hands (Left/Right)
- Legs and Feet (Left/Right)

## Troubleshooting

### Connection Issues
- Verify mocopi device and Blender are on the same network
- Check firewall settings for UDP port access
- Ensure port number matches between mocopi app and Blender

### Bone Mapping Problems
- Check armature bone names against supported naming conventions
- Use the bone mapping panel to manually assign bones if needed
- Ensure armature is in Rest Position before connecting

## Support

For technical support and questions, please join the following Discord server:

**Discord**: https://discord.gg/k55wY45y5N

## Resources

- **mocopi Official Developer Site**: [https://sony.net/mocopi-dev/](https://sony.net/mocopi-dev/)
- **Documentation**: [Blender Plugin Guide](https://www.sony.co.jp/en/Products/mocopi-dev/en/documents/ReceiverPlugin/Blender/AboutPlugin.html)

---

**Copyright © 2026 Sony Corporation. All rights reserved.**