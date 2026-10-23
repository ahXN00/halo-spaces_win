@echo off
rem halo.spaces – Installieren oder Deinstallieren mit einem Doppelklick (Logik in tools\install.ps1)
title halo.spaces for Windows
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\install.ps1" %*
