# Overview

## One line
Solavis is a solar-powered AI gate camera that recognises who is at the gate, alerts the owner, and locks itself if anyone moves, turns, covers or opens it, sold as a subscription from my own cloud.

## Short pitch (about 40 words)
A gate camera that runs on sunlight and knows who is at your door. It switches from Wi-Fi to 4G when the internet drops, and it locks itself and alerts you if anyone moves it. Built as a cloud service with plans, limits, remote control and a full company back office.

## Problem
- Gate cameras need mains power and cables; cheap ones only record and never say who is there.
- A camera at a gate can be turned, covered, moved or stolen, and the owner finds out late.
- Selling devices to many customers needs control: separated data, plans, limits, and a switch-off for non-paying accounts.
- A company running this needs a real back office with least-privilege access, not one shared admin.

## Solution (6 parts)
1. **Camera:** small wedge box, solar panel on a 15° slope, one lithium cell, PIR, accelerometer, compass, reed switch, white LED, 4G modem. Sleeps, wakes on motion.
2. **On-camera detect, cloud recognise:** the camera sends a small face crop; the cloud matches it against that customer's people and watch-list.
3. **Alerts:** web app and Telegram. Watch-list hits always say "possible match" and need human review.
4. **Network:** Wi-Fi first, 4G backup.
5. **Layered tamper protection:** ships unarmed; owner arms it at the final spot; any sign of movement locks it, takes a photo and alerts. Only the owner can unlock.
6. **Subscription control:** plans and limits are data; a suspended customer's camera stops uploading; the server checks every request.

## Two software products on one cloud
- **Customer app** (`/`): control devices, see visitors and alerts, tickets, billing.
- **Solavis ERP** (`/erp`): the company console. President with password + live face check; 8 departments each with a head; rights delegated within ceilings; tamper-evident audit log.

## Two product lines
1. Solavis Camera (first): hardware + subscription.
2. Solavis Platform (later): same cloud for customers' existing cameras via an on-site agent (concept).

## Role and timeline
Sole designer and engineer: product, hardware architecture, AI pipeline, backend, two web apps, security design, documentation, CAD scripting. Repository history 16 Sep to 26 Nov 2026. `[OWNER: confirm role title, dates, link, see questions-for-owner.md]`
