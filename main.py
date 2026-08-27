"""Discovery runs: search Indeed + ZipRecruiter, score results, and log them
to the database. Three sweeps, all using the same growing SEARCH_KEYWORDS
("specialization") list:
  - run_discovery():            local, distance-tiered around home base
  - run_remote_discovery():     nationwide/US-remote-tagged postings, high-selectivity
  - run_life_change_discovery(): nationwide relocation-open, salary-filtered

Honesty note on "international": Indeed/ZipRecruiter here are both the .com
(US) sites. Searching "Remote" surfaces some globally-open remote roles, but
this isn't real international job-board coverage — that would need querying
country-specific Indeed domains (indeed.co.uk, indeed.de, etc.), which isn't
built yet.

No applying happens here — that's the dashboard's job.
"""
import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from config import LIFE_CHANGE_SEARCH_RADIUS_MILES, LOCATION, SEARCH_KEYWORDS
from db.database import init_db, upsert_job, top_jobs
from matcher.scorer import score_job
from scrapers.abb import search_abb
from scrapers.ames import search_ames
from scrapers.analog_devices import search_analog_devices
from scrapers.anduril import search_anduril
from scrapers.anl import search_anl
from scrapers.applied_materials import search_applied_materials
from scrapers.aps import search_aps
from scrapers.asml import search_asml
from scrapers.atomcomputing import search_atomcomputing
from scrapers.bluefors import search_bluefors
from scrapers.bnl import search_bnl
from scrapers.boeing import search_boeing
from scrapers.bose import search_bose
from scrapers.boston_dynamics import search_boston_dynamics
from scrapers.clearancejobs import search_clearancejobs
from scrapers.coherent import search_coherent
from scrapers.commonwealth_fusion import search_commonwealth_fusion
from scrapers.corning import search_corning
from scrapers.deshaw import search_deshaw
from scrapers.draper import search_draper
from scrapers.dupont import search_dupont
from scrapers.fda import search_fda_orise
from scrapers.firefly_aerospace import search_firefly_aerospace
from scrapers.fnal import search_fnal
from scrapers.form_energy import search_form_energy
from scrapers.ge_healthcare import search_ge_healthcare
from scrapers.general_dynamics import search_general_dynamics
from scrapers.globalfoundries import search_globalfoundries
from scrapers.halliburton import search_halliburton
from scrapers.hamamatsu import search_hamamatsu
from scrapers.helion import search_helion
from scrapers.indeed import search_indeed
from scrapers.inl import search_inl
from scrapers.intel import search_intel
from scrapers.ionq import search_ionq
from scrapers.ipg_photonics import search_ipg_photonics
from scrapers.iridium import search_iridium
from scrapers.jane_street import search_jane_street
from scrapers.jlab import search_jlab
from scrapers.jump_trading import search_jump_trading
from scrapers.kairos_power import search_kairos_power
from scrapers.lanl import search_lanl
from scrapers.lbnl import search_lbnl
from scrapers.llnl import search_llnl
from scrapers.lockheed_martin import search_lockheed_martin
from scrapers.lumentum import search_lumentum
from scrapers.markforged import search_markforged
from scrapers.maxar import search_maxar
from scrapers.micron import search_micron
from scrapers.mitre import search_mitre
from scrapers.mks_instruments import search_mks_instruments
from scrapers.national_instruments import search_national_instruments
from scrapers.nlight import search_nlight
from scrapers.northrop_grumman import search_northrop_grumman
from scrapers.nrel import search_nrel
from scrapers.nuscale import search_nuscale
from scrapers.nvidia import search_nvidia
from scrapers.oklo import search_oklo
from scrapers.ornl import search_ornl
from scrapers.ouster import search_ouster
from scrapers.oxford_instruments import search_oxford_instruments
from scrapers.philips import search_philips
from scrapers.physicstoday import search_physicstoday
from scrapers.physicsworldjobs import search_physicsworldjobs
from scrapers.planet_labs import search_planet_labs
from scrapers.pnnl import search_pnnl
from scrapers.pppl import search_pppl
from scrapers.psiquantum import search_psiquantum
from scrapers.quantinuum import search_quantinuum
from scrapers.quantumscape import search_quantumscape
from scrapers.rigetti import search_rigetti
from scrapers.rocket_lab import search_rocket_lab
from scrapers.rockwell_automation import search_rockwell_automation
from scrapers.siemens_healthineers import search_siemens_healthineers
from scrapers.sierra_space import search_sierra_space
from scrapers.slac import search_slac
from scrapers.slb import search_slb
from scrapers.snl import search_snl
from scrapers.spacex import search_spacex
from scrapers.srnl import search_srnl
from scrapers.stratasys import search_stratasys
from scrapers.tae import search_tae
from scrapers.terrapower import search_terrapower
from scrapers.texas_instruments import search_texas_instruments
from scrapers.thorlabs import search_thorlabs
from scrapers.three_m import search_three_m
from scrapers.two_sigma import search_two_sigma
from scrapers.usajobs import search_usajobs
from scrapers.viasat import search_viasat
from scrapers.waymo import search_waymo
from scrapers.x_energy import search_x_energy
from scrapers.ziprecruiter import search_ziprecruiter

# ZipRecruiter auth: either a persistent browser profile from
# scrapers/ziprecruiter_login.py, or cookies exported from your own regular
# browser and converted with scrapers/convert_cookies.py. Cookies is the
# current path (login is Cloudflare-gated for automated browsers).
ZIPRECRUITER_PROFILE_DIR = Path(__file__).parent / "scrapers" / "ziprecruiter_profile"
ZIPRECRUITER_COOKIES_PATH = Path(__file__).parent / "scrapers" / "ziprecruiter_auth.json"


def _zip_auth_kwargs() -> dict:
    return {
        "profile_dir": str(ZIPRECRUITER_PROFILE_DIR) if ZIPRECRUITER_PROFILE_DIR.exists() else None,
        "storage_state_path": str(ZIPRECRUITER_COOKIES_PATH) if ZIPRECRUITER_COOKIES_PATH.exists() else None,
    }


VALID_SITES = {
    "indeed", "ziprecruiter", "usajobs", "aps",
    "pnnl", "anl", "fnal", "llnl", "lanl", "bnl", "slac", "ornl", "snl",
    "ames", "jlab", "pppl", "srnl", "nrel", "inl", "lbnl",
    "quantinuum", "physicstoday", "physicsworldjobs",
    "ionq", "anduril", "psiquantum", "boeing", "draper", "clearancejobs",
    "northrop_grumman", "lockheed_martin", "general_dynamics", "mitre", "spacex",
    "rigetti", "atomcomputing", "fda_orise",
    "coherent", "ipg_photonics", "thorlabs", "lumentum", "nlight",
    "mks_instruments", "hamamatsu",
    "intel", "texas_instruments", "micron", "applied_materials",
    "globalfoundries", "asml", "analog_devices", "nvidia",
    "commonwealth_fusion", "tae", "helion", "form_energy", "quantumscape",
    "x_energy", "terrapower", "oklo", "kairos_power", "nuscale",
    "siemens_healthineers", "ge_healthcare", "philips", "corning",
    "three_m", "dupont",
    "jane_street", "two_sigma", "deshaw", "jump_trading",
    "national_instruments",
    "slb", "halliburton", "boston_dynamics", "abb", "rockwell_automation",
    "bose",
    "ouster", "waymo", "rocket_lab", "sierra_space", "firefly_aerospace",
    "planet_labs", "maxar", "iridium", "viasat",
    "bluefors", "oxford_instruments", "stratasys", "markforged",
}


def _run_sweep(keywords: list[str], location_query: str, radius: int, mode: str,
                headless: bool, sites: list[str] | None = None) -> int:
    sites = set(sites) if sites else VALID_SITES
    unknown = sites - VALID_SITES
    if unknown:
        raise ValueError(f"Unknown site(s): {unknown}. Valid: {VALID_SITES}")

    total_found = 0
    for keyword in keywords:
        found_this_keyword = []

        if "indeed" in sites:
            print(f"[{mode}][indeed] searching: {keyword}")
            try:
                found_this_keyword += search_indeed(keyword, location_query, radius, headless=headless)
            except Exception as e:
                print(f"  indeed search failed for '{keyword}': {e}")

        if "ziprecruiter" in sites:
            print(f"[{mode}][ziprecruiter] searching: {keyword}")
            try:
                found_this_keyword += search_ziprecruiter(
                    keyword, location_query, radius, headless=headless, **_zip_auth_kwargs(),
                )
            except Exception as e:
                print(f"  ziprecruiter search failed for '{keyword}': {e}")

        if "usajobs" in sites:
            print(f"[{mode}][usajobs] searching: {keyword}")
            try:
                found_this_keyword += search_usajobs(keyword, location_query, radius)
            except Exception as e:
                print(f"  usajobs search failed for '{keyword}': {e}")

        if "pnnl" in sites:
            print(f"[{mode}][pnnl] searching: {keyword}")
            try:
                found_this_keyword += search_pnnl(keyword)
            except Exception as e:
                print(f"  pnnl search failed for '{keyword}': {e}")

        if "anl" in sites:
            print(f"[{mode}][anl] searching: {keyword}")
            try:
                found_this_keyword += search_anl(keyword)
            except Exception as e:
                print(f"  anl search failed for '{keyword}': {e}")

        if "fnal" in sites:
            print(f"[{mode}][fnal] searching: {keyword}")
            try:
                found_this_keyword += search_fnal(keyword)
            except Exception as e:
                print(f"  fnal search failed for '{keyword}': {e}")

        if "aps" in sites:
            print(f"[{mode}][aps] searching: {keyword}")
            try:
                found_this_keyword += search_aps(keyword)
            except Exception as e:
                print(f"  aps search failed for '{keyword}': {e}")

        if "llnl" in sites:
            print(f"[{mode}][llnl] searching: {keyword}")
            try:
                found_this_keyword += search_llnl(keyword)
            except Exception as e:
                print(f"  llnl search failed for '{keyword}': {e}")

        if "lanl" in sites:
            print(f"[{mode}][lanl] searching: {keyword}")
            try:
                found_this_keyword += search_lanl(keyword)
            except Exception as e:
                print(f"  lanl search failed for '{keyword}': {e}")

        if "bnl" in sites:
            print(f"[{mode}][bnl] searching: {keyword}")
            try:
                found_this_keyword += search_bnl(keyword)
            except Exception as e:
                print(f"  bnl search failed for '{keyword}': {e}")

        if "slac" in sites:
            print(f"[{mode}][slac] searching: {keyword}")
            try:
                found_this_keyword += search_slac(keyword)
            except Exception as e:
                print(f"  slac search failed for '{keyword}': {e}")

        if "ornl" in sites:
            print(f"[{mode}][ornl] searching: {keyword}")
            try:
                found_this_keyword += search_ornl(keyword)
            except Exception as e:
                print(f"  ornl search failed for '{keyword}': {e}")

        if "snl" in sites:
            print(f"[{mode}][snl] searching: {keyword}")
            try:
                found_this_keyword += search_snl(keyword, headless=headless)
            except Exception as e:
                print(f"  snl search failed for '{keyword}': {e}")

        if "ames" in sites:
            print(f"[{mode}][ames] searching: {keyword}")
            try:
                found_this_keyword += search_ames(keyword)
            except Exception as e:
                print(f"  ames search failed for '{keyword}': {e}")

        if "jlab" in sites:
            print(f"[{mode}][jlab] searching: {keyword}")
            try:
                found_this_keyword += search_jlab(keyword)
            except Exception as e:
                print(f"  jlab search failed for '{keyword}': {e}")

        if "pppl" in sites:
            print(f"[{mode}][pppl] searching: {keyword}")
            try:
                found_this_keyword += search_pppl(keyword)
            except Exception as e:
                print(f"  pppl search failed for '{keyword}': {e}")

        if "srnl" in sites:
            print(f"[{mode}][srnl] searching: {keyword}")
            try:
                found_this_keyword += search_srnl(keyword)
            except Exception as e:
                print(f"  srnl search failed for '{keyword}': {e}")

        if "nrel" in sites:
            print(f"[{mode}][nrel] searching: {keyword}")
            try:
                found_this_keyword += search_nrel(keyword)
            except Exception as e:
                print(f"  nrel search failed for '{keyword}': {e}")

        if "inl" in sites:
            print(f"[{mode}][inl] searching: {keyword}")
            try:
                found_this_keyword += search_inl(keyword, headless=headless)
            except Exception as e:
                print(f"  inl search failed for '{keyword}': {e}")

        if "lbnl" in sites:
            print(f"[{mode}][lbnl] searching: {keyword}")
            try:
                found_this_keyword += search_lbnl(keyword, headless=headless)
            except Exception as e:
                print(f"  lbnl search failed for '{keyword}': {e}")

        if "quantinuum" in sites:
            print(f"[{mode}][quantinuum] searching: {keyword}")
            try:
                found_this_keyword += search_quantinuum(keyword)
            except Exception as e:
                print(f"  quantinuum search failed for '{keyword}': {e}")

        if "physicstoday" in sites:
            print(f"[{mode}][physicstoday] searching: {keyword}")
            try:
                found_this_keyword += search_physicstoday(keyword)
            except Exception as e:
                print(f"  physicstoday search failed for '{keyword}': {e}")

        if "physicsworldjobs" in sites:
            print(f"[{mode}][physicsworldjobs] searching: {keyword}")
            try:
                found_this_keyword += search_physicsworldjobs(keyword)
            except Exception as e:
                print(f"  physicsworldjobs search failed for '{keyword}': {e}")

        if "ionq" in sites:
            print(f"[{mode}][ionq] searching: {keyword}")
            try:
                found_this_keyword += search_ionq(keyword)
            except Exception as e:
                print(f"  ionq search failed for '{keyword}': {e}")

        if "anduril" in sites:
            print(f"[{mode}][anduril] searching: {keyword}")
            try:
                found_this_keyword += search_anduril(keyword)
            except Exception as e:
                print(f"  anduril search failed for '{keyword}': {e}")

        if "psiquantum" in sites:
            print(f"[{mode}][psiquantum] searching: {keyword}")
            try:
                found_this_keyword += search_psiquantum(keyword)
            except Exception as e:
                print(f"  psiquantum search failed for '{keyword}': {e}")

        if "boeing" in sites:
            print(f"[{mode}][boeing] searching: {keyword}")
            try:
                found_this_keyword += search_boeing(keyword)
            except Exception as e:
                print(f"  boeing search failed for '{keyword}': {e}")

        if "draper" in sites:
            print(f"[{mode}][draper] searching: {keyword}")
            try:
                found_this_keyword += search_draper(keyword)
            except Exception as e:
                print(f"  draper search failed for '{keyword}': {e}")

        if "clearancejobs" in sites:
            print(f"[{mode}][clearancejobs] searching: {keyword}")
            try:
                found_this_keyword += search_clearancejobs(keyword, location_query, radius)
            except Exception as e:
                print(f"  clearancejobs search failed for '{keyword}': {e}")

        if "northrop_grumman" in sites:
            print(f"[{mode}][northrop_grumman] searching: {keyword}")
            try:
                found_this_keyword += search_northrop_grumman(keyword)
            except Exception as e:
                print(f"  northrop_grumman search failed for '{keyword}': {e}")

        if "lockheed_martin" in sites:
            print(f"[{mode}][lockheed_martin] searching: {keyword}")
            try:
                found_this_keyword += search_lockheed_martin(keyword)
            except Exception as e:
                print(f"  lockheed_martin search failed for '{keyword}': {e}")

        if "general_dynamics" in sites:
            print(f"[{mode}][general_dynamics] searching: {keyword}")
            try:
                found_this_keyword += search_general_dynamics(keyword)
            except Exception as e:
                print(f"  general_dynamics search failed for '{keyword}': {e}")

        if "mitre" in sites:
            print(f"[{mode}][mitre] searching: {keyword}")
            try:
                found_this_keyword += search_mitre(keyword)
            except Exception as e:
                print(f"  mitre search failed for '{keyword}': {e}")

        if "spacex" in sites:
            print(f"[{mode}][spacex] searching: {keyword}")
            try:
                found_this_keyword += search_spacex(keyword)
            except Exception as e:
                print(f"  spacex search failed for '{keyword}': {e}")

        if "rigetti" in sites:
            print(f"[{mode}][rigetti] searching: {keyword}")
            try:
                found_this_keyword += search_rigetti(keyword)
            except Exception as e:
                print(f"  rigetti search failed for '{keyword}': {e}")

        if "atomcomputing" in sites:
            print(f"[{mode}][atomcomputing] searching: {keyword}")
            try:
                found_this_keyword += search_atomcomputing(keyword)
            except Exception as e:
                print(f"  atomcomputing search failed for '{keyword}': {e}")

        if "fda_orise" in sites:
            print(f"[{mode}][fda_orise] searching: {keyword}")
            try:
                found_this_keyword += search_fda_orise(keyword)
            except Exception as e:
                print(f"  fda_orise search failed for '{keyword}': {e}")

        if "coherent" in sites:
            print(f"[{mode}][coherent] searching: {keyword}")
            try:
                found_this_keyword += search_coherent(keyword)
            except Exception as e:
                print(f"  coherent search failed for '{keyword}': {e}")

        if "ipg_photonics" in sites:
            print(f"[{mode}][ipg_photonics] searching: {keyword}")
            try:
                found_this_keyword += search_ipg_photonics(keyword)
            except Exception as e:
                print(f"  ipg_photonics search failed for '{keyword}': {e}")

        if "thorlabs" in sites:
            print(f"[{mode}][thorlabs] searching: {keyword}")
            try:
                found_this_keyword += search_thorlabs(keyword)
            except Exception as e:
                print(f"  thorlabs search failed for '{keyword}': {e}")

        if "lumentum" in sites:
            print(f"[{mode}][lumentum] searching: {keyword}")
            try:
                found_this_keyword += search_lumentum(keyword)
            except Exception as e:
                print(f"  lumentum search failed for '{keyword}': {e}")

        if "nlight" in sites:
            print(f"[{mode}][nlight] searching: {keyword}")
            try:
                found_this_keyword += search_nlight(keyword)
            except Exception as e:
                print(f"  nlight search failed for '{keyword}': {e}")

        if "mks_instruments" in sites:
            print(f"[{mode}][mks_instruments] searching: {keyword}")
            try:
                found_this_keyword += search_mks_instruments(keyword)
            except Exception as e:
                print(f"  mks_instruments search failed for '{keyword}': {e}")

        if "hamamatsu" in sites:
            print(f"[{mode}][hamamatsu] searching: {keyword}")
            try:
                found_this_keyword += search_hamamatsu(keyword)
            except Exception as e:
                print(f"  hamamatsu search failed for '{keyword}': {e}")

        if "intel" in sites:
            print(f"[{mode}][intel] searching: {keyword}")
            try:
                found_this_keyword += search_intel(keyword)
            except Exception as e:
                print(f"  intel search failed for '{keyword}': {e}")

        if "texas_instruments" in sites:
            print(f"[{mode}][texas_instruments] searching: {keyword}")
            try:
                found_this_keyword += search_texas_instruments(keyword)
            except Exception as e:
                print(f"  texas_instruments search failed for '{keyword}': {e}")

        if "micron" in sites:
            print(f"[{mode}][micron] searching: {keyword}")
            try:
                found_this_keyword += search_micron(keyword)
            except Exception as e:
                print(f"  micron search failed for '{keyword}': {e}")

        if "applied_materials" in sites:
            print(f"[{mode}][applied_materials] searching: {keyword}")
            try:
                found_this_keyword += search_applied_materials(keyword)
            except Exception as e:
                print(f"  applied_materials search failed for '{keyword}': {e}")

        if "globalfoundries" in sites:
            print(f"[{mode}][globalfoundries] searching: {keyword}")
            try:
                found_this_keyword += search_globalfoundries(keyword)
            except Exception as e:
                print(f"  globalfoundries search failed for '{keyword}': {e}")

        if "asml" in sites:
            print(f"[{mode}][asml] searching: {keyword}")
            try:
                found_this_keyword += search_asml(keyword)
            except Exception as e:
                print(f"  asml search failed for '{keyword}': {e}")

        if "analog_devices" in sites:
            print(f"[{mode}][analog_devices] searching: {keyword}")
            try:
                found_this_keyword += search_analog_devices(keyword)
            except Exception as e:
                print(f"  analog_devices search failed for '{keyword}': {e}")

        if "nvidia" in sites:
            print(f"[{mode}][nvidia] searching: {keyword}")
            try:
                found_this_keyword += search_nvidia(keyword)
            except Exception as e:
                print(f"  nvidia search failed for '{keyword}': {e}")

        if "commonwealth_fusion" in sites:
            print(f"[{mode}][commonwealth_fusion] searching: {keyword}")
            try:
                found_this_keyword += search_commonwealth_fusion(keyword)
            except Exception as e:
                print(f"  commonwealth_fusion search failed for '{keyword}': {e}")

        if "tae" in sites:
            print(f"[{mode}][tae] searching: {keyword}")
            try:
                found_this_keyword += search_tae(keyword)
            except Exception as e:
                print(f"  tae search failed for '{keyword}': {e}")

        if "helion" in sites:
            print(f"[{mode}][helion] searching: {keyword}")
            try:
                found_this_keyword += search_helion(keyword)
            except Exception as e:
                print(f"  helion search failed for '{keyword}': {e}")

        if "form_energy" in sites:
            print(f"[{mode}][form_energy] searching: {keyword}")
            try:
                found_this_keyword += search_form_energy(keyword)
            except Exception as e:
                print(f"  form_energy search failed for '{keyword}': {e}")

        if "quantumscape" in sites:
            print(f"[{mode}][quantumscape] searching: {keyword}")
            try:
                found_this_keyword += search_quantumscape(keyword)
            except Exception as e:
                print(f"  quantumscape search failed for '{keyword}': {e}")

        if "x_energy" in sites:
            print(f"[{mode}][x_energy] searching: {keyword}")
            try:
                found_this_keyword += search_x_energy(keyword)
            except Exception as e:
                print(f"  x_energy search failed for '{keyword}': {e}")

        if "terrapower" in sites:
            print(f"[{mode}][terrapower] searching: {keyword}")
            try:
                found_this_keyword += search_terrapower(keyword)
            except Exception as e:
                print(f"  terrapower search failed for '{keyword}': {e}")

        if "oklo" in sites:
            print(f"[{mode}][oklo] searching: {keyword}")
            try:
                found_this_keyword += search_oklo(keyword)
            except Exception as e:
                print(f"  oklo search failed for '{keyword}': {e}")

        if "kairos_power" in sites:
            print(f"[{mode}][kairos_power] searching: {keyword}")
            try:
                found_this_keyword += search_kairos_power(keyword)
            except Exception as e:
                print(f"  kairos_power search failed for '{keyword}': {e}")

        if "nuscale" in sites:
            print(f"[{mode}][nuscale] searching: {keyword}")
            try:
                found_this_keyword += search_nuscale(keyword)
            except Exception as e:
                print(f"  nuscale search failed for '{keyword}': {e}")

        if "siemens_healthineers" in sites:
            print(f"[{mode}][siemens_healthineers] searching: {keyword}")
            try:
                found_this_keyword += search_siemens_healthineers(keyword)
            except Exception as e:
                print(f"  siemens_healthineers search failed for '{keyword}': {e}")

        if "ge_healthcare" in sites:
            print(f"[{mode}][ge_healthcare] searching: {keyword}")
            try:
                found_this_keyword += search_ge_healthcare(keyword)
            except Exception as e:
                print(f"  ge_healthcare search failed for '{keyword}': {e}")

        if "philips" in sites:
            print(f"[{mode}][philips] searching: {keyword}")
            try:
                found_this_keyword += search_philips(keyword)
            except Exception as e:
                print(f"  philips search failed for '{keyword}': {e}")

        if "corning" in sites:
            print(f"[{mode}][corning] searching: {keyword}")
            try:
                found_this_keyword += search_corning(keyword)
            except Exception as e:
                print(f"  corning search failed for '{keyword}': {e}")

        if "three_m" in sites:
            print(f"[{mode}][three_m] searching: {keyword}")
            try:
                found_this_keyword += search_three_m(keyword)
            except Exception as e:
                print(f"  three_m search failed for '{keyword}': {e}")

        if "dupont" in sites:
            print(f"[{mode}][dupont] searching: {keyword}")
            try:
                found_this_keyword += search_dupont(keyword)
            except Exception as e:
                print(f"  dupont search failed for '{keyword}': {e}")

        if "jane_street" in sites:
            print(f"[{mode}][jane_street] searching: {keyword}")
            try:
                found_this_keyword += search_jane_street(keyword)
            except Exception as e:
                print(f"  jane_street search failed for '{keyword}': {e}")

        if "two_sigma" in sites:
            print(f"[{mode}][two_sigma] searching: {keyword}")
            try:
                found_this_keyword += search_two_sigma(keyword)
            except Exception as e:
                print(f"  two_sigma search failed for '{keyword}': {e}")

        if "deshaw" in sites:
            print(f"[{mode}][deshaw] searching: {keyword}")
            try:
                found_this_keyword += search_deshaw(keyword)
            except Exception as e:
                print(f"  deshaw search failed for '{keyword}': {e}")

        if "jump_trading" in sites:
            print(f"[{mode}][jump_trading] searching: {keyword}")
            try:
                found_this_keyword += search_jump_trading(keyword)
            except Exception as e:
                print(f"  jump_trading search failed for '{keyword}': {e}")

        if "national_instruments" in sites:
            print(f"[{mode}][national_instruments] searching: {keyword}")
            try:
                found_this_keyword += search_national_instruments(keyword)
            except Exception as e:
                print(f"  national_instruments search failed for '{keyword}': {e}")

        if "slb" in sites:
            print(f"[{mode}][slb] searching: {keyword}")
            try:
                found_this_keyword += search_slb(keyword)
            except Exception as e:
                print(f"  slb search failed for '{keyword}': {e}")

        if "halliburton" in sites:
            print(f"[{mode}][halliburton] searching: {keyword}")
            try:
                found_this_keyword += search_halliburton(keyword)
            except Exception as e:
                print(f"  halliburton search failed for '{keyword}': {e}")

        if "boston_dynamics" in sites:
            print(f"[{mode}][boston_dynamics] searching: {keyword}")
            try:
                found_this_keyword += search_boston_dynamics(keyword)
            except Exception as e:
                print(f"  boston_dynamics search failed for '{keyword}': {e}")

        if "abb" in sites:
            print(f"[{mode}][abb] searching: {keyword}")
            try:
                found_this_keyword += search_abb(keyword)
            except Exception as e:
                print(f"  abb search failed for '{keyword}': {e}")

        if "rockwell_automation" in sites:
            print(f"[{mode}][rockwell_automation] searching: {keyword}")
            try:
                found_this_keyword += search_rockwell_automation(keyword)
            except Exception as e:
                print(f"  rockwell_automation search failed for '{keyword}': {e}")

        if "bose" in sites:
            print(f"[{mode}][bose] searching: {keyword}")
            try:
                found_this_keyword += search_bose(keyword)
            except Exception as e:
                print(f"  bose search failed for '{keyword}': {e}")

        if "ouster" in sites:
            print(f"[{mode}][ouster] searching: {keyword}")
            try:
                found_this_keyword += search_ouster(keyword)
            except Exception as e:
                print(f"  ouster search failed for '{keyword}': {e}")

        if "waymo" in sites:
            print(f"[{mode}][waymo] searching: {keyword}")
            try:
                found_this_keyword += search_waymo(keyword)
            except Exception as e:
                print(f"  waymo search failed for '{keyword}': {e}")

        if "rocket_lab" in sites:
            print(f"[{mode}][rocket_lab] searching: {keyword}")
            try:
                found_this_keyword += search_rocket_lab(keyword)
            except Exception as e:
                print(f"  rocket_lab search failed for '{keyword}': {e}")

        if "sierra_space" in sites:
            print(f"[{mode}][sierra_space] searching: {keyword}")
            try:
                found_this_keyword += search_sierra_space(keyword)
            except Exception as e:
                print(f"  sierra_space search failed for '{keyword}': {e}")

        if "firefly_aerospace" in sites:
            print(f"[{mode}][firefly_aerospace] searching: {keyword}")
            try:
                found_this_keyword += search_firefly_aerospace(keyword)
            except Exception as e:
                print(f"  firefly_aerospace search failed for '{keyword}': {e}")

        if "planet_labs" in sites:
            print(f"[{mode}][planet_labs] searching: {keyword}")
            try:
                found_this_keyword += search_planet_labs(keyword)
            except Exception as e:
                print(f"  planet_labs search failed for '{keyword}': {e}")

        if "maxar" in sites:
            print(f"[{mode}][maxar] searching: {keyword}")
            try:
                found_this_keyword += search_maxar(keyword)
            except Exception as e:
                print(f"  maxar search failed for '{keyword}': {e}")

        if "iridium" in sites:
            print(f"[{mode}][iridium] searching: {keyword}")
            try:
                found_this_keyword += search_iridium(keyword)
            except Exception as e:
                print(f"  iridium search failed for '{keyword}': {e}")

        if "viasat" in sites:
            print(f"[{mode}][viasat] searching: {keyword}")
            try:
                found_this_keyword += search_viasat(keyword)
            except Exception as e:
                print(f"  viasat search failed for '{keyword}': {e}")

        if "bluefors" in sites:
            print(f"[{mode}][bluefors] searching: {keyword}")
            try:
                found_this_keyword += search_bluefors(keyword)
            except Exception as e:
                print(f"  bluefors search failed for '{keyword}': {e}")

        if "oxford_instruments" in sites:
            print(f"[{mode}][oxford_instruments] searching: {keyword}")
            try:
                found_this_keyword += search_oxford_instruments(keyword)
            except Exception as e:
                print(f"  oxford_instruments search failed for '{keyword}': {e}")

        if "stratasys" in sites:
            print(f"[{mode}][stratasys] searching: {keyword}")
            try:
                found_this_keyword += search_stratasys(keyword)
            except Exception as e:
                print(f"  stratasys search failed for '{keyword}': {e}")

        if "markforged" in sites:
            print(f"[{mode}][markforged] searching: {keyword}")
            try:
                found_this_keyword += search_markforged(keyword)
            except Exception as e:
                print(f"  markforged search failed for '{keyword}': {e}")

        for job in found_this_keyword:
            result = score_job(
                job["title"], job.get("snippet", ""), job.get("location"),
                mode=mode, salary=job.get("salary"),
            )
            job.update(result)
            job["search_mode"] = mode
            upsert_job(job)
            total_found += 1

        time.sleep(3)  # space out requests between keywords

    return total_found


def run_discovery(keywords=None, headless: bool = True, sites: list[str] | None = None):
    """Local sweep: distance-tiered around home base."""
    init_db()
    keywords = keywords or SEARCH_KEYWORDS
    total = _run_sweep(keywords, LOCATION["query"], LOCATION["radius_miles"], "local", headless, sites)
    print(f"\n[local] Done. {total} listings processed this run.")


def run_remote_discovery(keywords=None, headless: bool = True, sites: list[str] | None = None):
    """Nationwide/US-remote sweep, high-selectivity (REMOTE_MIN_SCORE)."""
    init_db()
    keywords = keywords or SEARCH_KEYWORDS
    # radius is meaningless for "Remote" as a location, but pass a large
    # value rather than 0 — untested whether either site would interpret
    # radius=0 as "exact point only" and over-narrow results.
    total = _run_sweep(keywords, "Remote", 100, "remote", headless, sites)
    print(f"\n[remote] Done. {total} listings processed this run.")


def run_life_change_discovery(keywords=None, headless: bool = True, sites: list[str] | None = None):
    """Nationwide relocation-open sweep, filtered on relevance + pay."""
    init_db()
    keywords = keywords or SEARCH_KEYWORDS
    total = _run_sweep(keywords, "United States", LIFE_CHANGE_SEARCH_RADIUS_MILES, "life_change", headless, sites)
    print(f"\n[life_change] Done. {total} listings processed this run.")


if __name__ == "__main__":
    run_discovery()
    print("\nTop scoring jobs so far:")
    for j in top_jobs(limit=15):
        print(f"  [{j['score']:>4}] {j['title']} — {j['company']} ({j['source']}) — {j['application_status']}")
