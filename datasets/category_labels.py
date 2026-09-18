"""
Canonical aesthetic-category labels for the AgentWeave fashion dataset.

Filenames in datasets/rawImages/ encode a weak category label as a
truncated prefix (e.g. "boho_beach_9.jpg", "techwear_o_3.jpg" — truncated
because the scraper used a fixed-width slug). This module maps each of the
24 filename prefixes to both a short canonical label (used everywhere as
the category id) and a natural-language phrase suitable as a CLIP zero-shot
text prompt.
"""

# filename prefix -> canonical short label
PREFIX_TO_LABEL = {
    "minimalist": "minimalist",
    "business_c": "business_casual",
    "Indian_eth": "indian_ethnic",
    "modest_fas": "modest",
    "techwear_o": "techwear_outerwear",
    "techwear_m": "techwear_minimal",
    "retro_summ": "retro_summer",
    "preppy_sch": "preppy_school",
    "evening_go": "evening_gown",
    "boho_beach": "boho_beach",
    "e-girl_aes": "egirl_aesthetic",
    "Y2K_pastel": "y2k_pastel",
    "summer_fes": "summer_festival",
    "plus-size_": "plus_size",
    "officewear": "officewear",
    "monochrome": "monochrome",
    "gender-neu": "gender_neutral",
    "cottagecor": "cottagecore",
    "vintage_90": "vintage_90s",
    "quiet_luxu": "quiet_luxury",
    "grunge_pun": "grunge_punk",
    "rainy_day_": "rainy_day",
    "layered_fa": "layered",
    "denim-on-d": "denim_on_denim",
    "athleisure": "athleisure",
    "Korean_str": "korean_street",
}

# canonical short label -> natural-language CLIP text prompt
LABEL_TO_PROMPT = {
    "minimalist": "a photo of minimalist fashion, clean simple outfit",
    "business_casual": "a photo of business casual fashion outfit",
    "indian_ethnic": "a photo of Indian ethnic fashion, traditional outfit",
    "modest": "a photo of modest fashion, covered conservative outfit",
    "techwear_outerwear": "a photo of techwear outerwear, technical jacket outfit",
    "techwear_minimal": "a photo of minimalist techwear fashion outfit",
    "retro_summer": "a photo of retro summer fashion outfit",
    "preppy_school": "a photo of preppy schoolgirl/schoolboy fashion outfit",
    "evening_gown": "a photo of an evening gown, formal fashion outfit",
    "boho_beach": "a photo of boho beach fashion, bohemian outfit",
    "egirl_aesthetic": "a photo of e-girl aesthetic fashion outfit",
    "y2k_pastel": "a photo of Y2K pastel fashion outfit",
    "summer_festival": "a photo of summer festival fashion outfit",
    "plus_size": "a photo of plus-size fashion outfit",
    "officewear": "a photo of office wear fashion, professional outfit",
    "monochrome": "a photo of monochrome fashion, single-color outfit",
    "gender_neutral": "a photo of gender-neutral fashion outfit",
    "cottagecore": "a photo of cottagecore fashion, rustic pastoral outfit",
    "vintage_90s": "a photo of vintage 1990s fashion outfit",
    "quiet_luxury": "a photo of quiet luxury fashion, understated expensive outfit",
    "grunge_punk": "a photo of grunge punk fashion outfit",
    "rainy_day": "a photo of rainy day fashion, outfit with raincoat or boots",
    "layered": "a photo of layered fashion, outfit with multiple layers",
    "denim_on_denim": "a photo of denim-on-denim fashion, double denim outfit",
    "athleisure": "a photo of athleisure fashion, athletic leisure outfit",
    "korean_street": "a photo of Korean street fashion outfit",
}

# NOTE: exploration during planning estimated "~24 categories"; the actual
# filename-prefix census below found 26 distinct prefixes in datasets/rawImages.
# Trusting the real data over the earlier estimate.
LABELS = list(PREFIX_TO_LABEL.values())
assert len(set(LABELS)) == len(LABELS) == 26, "expected 26 unique canonical labels"
assert set(LABELS) == set(LABEL_TO_PROMPT.keys())


def label_from_filename(filename: str) -> str:
    """Derive the weak filename-encoded label for a raw dataset filename."""
    base = filename.rsplit(".", 1)[0]
    # prefixes are the fixed-width slug before the trailing _<number>
    for prefix, label in PREFIX_TO_LABEL.items():
        if base.startswith(prefix):
            return label
    raise ValueError(f"Unrecognized filename prefix for {filename!r}")
