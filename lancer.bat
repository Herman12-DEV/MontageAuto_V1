@echo off
rem Lance AutoCut en local (backend + site) et ouvre le navigateur quand tout est pret.
rem Ctrl + C dans cette fenetre arrete tout.
title AutoCut
cd /d "%~dp0"
npm start
