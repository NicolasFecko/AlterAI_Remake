"""
Hello Everyone reading this code, I am Nicolas Fecko and this is my AlterAI program.
In short I wanted to make an alternative approach to Artifficial intelligence by giving Alter a Purpose in Mental health.
It runs a local model of gemma3:4b and initializes its custom personality via a personality prompt.

I am essentially rewriting and polishing a program I already made for ISEF Košice 2025
"""
# --- Imports ---
from ollama import Client
import json
import os
import customtkinter as tk

# Basic Setup
client = Client(host='http://localhost:11434')
MODEL_NAME = 'gemma3:4b' # The base Language model to be used     
# Model gemma3:4b Multilingual model of 4 Billion parameters. Speaks over 70 languages
MEMORY_FILE = 'memory_ISEF.json' # Where to store memory
SETTINGS_FILE = "settings.json" # Where to store settings

# Test line