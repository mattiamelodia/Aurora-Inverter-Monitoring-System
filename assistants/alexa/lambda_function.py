import json
import urllib.request

def lambda_handler(event, context):
    """
    Look at the name of the intent and call the right function to handle it.
    """
    request_type = event["request"]["type"]

    if request_type == "LaunchRequest":
        welcome_text = "Ciao! Puoi chiedermi la potenza attuale o la produzione di oggi."
        return build_response(speech_text=welcome_text, should_end_session=False)

    elif request_type == "IntentRequest":
        intent_name = event["request"]["intent"]["name"]

        if intent_name == "GetInverterPowerIntent":
            return handle_get_inverter_power()
            
        elif intent_name == "GetDailyEnergyIntent":
            return handle_get_daily_energy()
            
        elif intent_name in ["AMAZON.StopIntent", "AMAZON.CancelIntent"]:
            return build_response(speech_text="A presto!", should_end_session=True)

    return build_response(speech_text="Scusa, non ho capito. Cosa vuoi sapere?", should_end_session=False)


def handle_get_inverter_power():
    """
    Handle the request for current power and converts it to KILOWATT.
    """
    api_url = "https://api-inverter.esp32.ip-ddns.com/api/power"
    try:
        with urllib.request.urlopen(api_url) as response:
            data = json.loads(response.read())
            raw_power_watt = data.get("power_in_total")
            
            if isinstance(raw_power_watt, (int, float)):
                power_kilowatt = raw_power_watt / 1000
                rounded_kilowatt = round(power_kilowatt, 2)
                speech_text = f"L'inverter sta producendo circa {rounded_kilowatt} kilowatt."
            else:
                speech_text = "Non riesco a leggere il dato sulla potenza."
    except Exception:
        speech_text = "Non riesco a contattare il server per la potenza attuale."
    
    return build_response(speech_text=speech_text, should_end_session=False)


def handle_get_daily_energy():
    """
    Handle the request for daily energy and converts it to KILOWATTORA.
    """
    api_url = "https://api-inverter.esp32.ip-ddns.com/api/energy/today"
    try:
        with urllib.request.urlopen(api_url) as response:
            data = json.loads(response.read())
            raw_daily_energy_wh = data.get("cumulated_energy_today") 
            
            if isinstance(raw_daily_energy_wh, (int, float)):
                daily_energy_kwh = raw_daily_energy_wh / 1000
                
                rounded_energy = round(daily_energy_kwh, 2)
                
                speech_text = f"L'inverter oggi ha prodotto circa {rounded_energy} kilowattora."
            else:
                speech_text = "Non riesco a leggere il dato sull'energia giornaliera."
    except Exception:
        speech_text = "Non riesco a contattare il server per il totale giornaliero."

    return build_response(speech_text=speech_text, should_end_session=False)


def build_response(speech_text, should_end_session):
    """
    Builds the JSON response for Alexa.
    """
    return {
        "version": "1.0",
        "response": {
            "outputSpeech": {
                "type": "PlainText",
                "text": speech_text
            },
            "shouldEndSession": should_end_session
        }
    }