from __future__ import annotations

import hashlib
import json
import os
import random
import re
from datetime import datetime
from typing import Any
from urllib.parse import quote_plus

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, session
from groq import Groq

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "ai-car-concept-lab-dev-key")
app.config["SESSION_PERMANENT"] = False

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
HCAPTCHA_SITE_KEY = os.environ.get("HCAPTCHA_SITE_KEY", "")
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
MAX_HISTORY = 12

STYLE_TAGS = {
    "Hypercar": ["aggressive aero", "track-born drama", "hero stance"],
    "Luxury": ["quiet prestige", "clean surfacing", "executive cabin"],
    "Off-Road": ["all-terrain muscle", "raised stance", "rugged utility"],
    "EV": ["clean tech", "silent thrust", "future cockpit"],
    "Retro-Future": ["heritage remix", "neo-classic curves", "concept nostalgia"],
    "Street": ["night-run energy", "urban custom", "after-dark attitude"],
}

MATERIAL_NOTES = {
    "Carbon Fiber": ["carbon composite shell", "forged aero fins", "lightweight chassis"],
    "Aluminum": ["aluminum body frame", "precision-machined trim", "satin shell panels"],
    "Titanium": ["titanium highlights", "heat-blued metal details", "ultra-premium structural spine"],
    "Recycled Composite": ["recycled composite shell", "eco-performance weave", "sustainable cabin accents"],
    "Glass & Metal": ["glass canopy roof", "brushed alloy bodywork", "framed light signature"],
    "Mixed Performance": ["hybrid material shell", "performance mesh venting", "contrasting aero textures"],
}

PRICE_BANDS = {
    "Daily Drive": "$58,000",
    "Track Day": "$210,000",
    "Adventure": "$96,000",
    "Collector Reveal": "$320,000",
    "City Tech": "$74,000",
    "Luxury Tourer": "$168,000",
}

DESIGN_PROMPT = """You are a visionary automotive concept designer.
Generate a complete futuristic car concept based on:
Style: {style}
Primary Color: {primary_color}
Accent Color: {accent_color}
Material: {material}
Occasion: {occasion}
Inspiration: {inspiration}

Respond with raw JSON only — no markdown, no explanation.
{{
  "name": "2-4 word creative car name",
  "tagline": "punchy tagline max 10 words",
  "description": "2-3 sentence cinematic concept description",
  "materials": ["mat1", "mat2", "mat3"],
  "colorways": [
    {{"name": "launch spec", "body": "#hex", "accent": "#hex", "wheels": "#hex", "cabin": "#hex"}}
  ],
  "features": ["feat1", "feat2", "feat3", "feat4"],
  "powertrain": "power system description",
  "cockpit_theme": "cockpit mood and interface idea",
  "target_driver": "who this concept is for",
  "retail_price": "$XXX,XXX",
  "style_tags": ["tag1", "tag2", "tag3"]
}}
Generate exactly 3 colorways. All hex codes must be valid #RRGGBB."""


@app.route("/")
def index() -> str:
    return render_template("index.html")


@app.route("/studio")
def studio() -> str:
    return render_template("studio.html", hcaptcha_site_key=HCAPTCHA_SITE_KEY)


@app.route("/history")
def history() -> str:
    return render_template("history.html", designs=get_history())


@app.route("/generate", methods=["POST"])
def generate() -> Any:
    data = request.get_json(silent=True) or request.form
    prefs = get_prefs(data)
    if any(not v for v in prefs.values()):
        return jsonify({"error": "Please complete every field in the design brief."}), 400

    try:
        concept = generate_concept(prefs)
    except json.JSONDecodeError as exc:
        return jsonify({"error": f"Malformed AI response: {exc}"}), 500
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"Concept generation failed: {exc}"}), 500

    concept["image_url"] = build_image_url(concept, prefs)
    concept["brief"] = prefs
    concept["timestamp"] = datetime.now().strftime("%d %b %Y, %I:%M %p")
    concept["fingerprint"] = fingerprint(prefs, concept["name"])
    add_to_history(concept)
    return jsonify({"success": True, "concept": concept, "prefs": prefs})


@app.route("/clear-history", methods=["POST"])
def clear_history() -> Any:
    session["designs"]
