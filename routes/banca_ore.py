from flask import Blueprint, redirect, url_for

banca_ore_bp = Blueprint("banca_ore", __name__)

@banca_ore_bp.route("/banca-ore")
def index():
    return redirect(url_for("report.index"))
