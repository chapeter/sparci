import json
from textwrap import dedent

import click
import requests
import websocket
from requests.packages import urllib3
from spark.rooms import Room
from spark.session import Session

urllib3.disable_warnings()


@click.command()
@click.option('--spark-key', help="Your Spark API key\n(available at developer.ciscospark.com)", prompt=True,
              hide_input=True)
@click.option('--spark-room', help="The room you wish updates to be posted to", prompt=True)
@click.option('--apic-address', help="DNS or IP address of your APIC", prompt=True)
@click.option('--apic-user', help="User with enough priviledges to read aaaModLR", prompt=True)
@click.option('--apic-pass', help="APIC user password", prompt=True, hide_input=True, confirmation_prompt=True)
@click.option('--debug', help="Show detailed websocket information")
def sparci(spark_key, spark_room, apic_address, apic_user, apic_pass, debug=False):
    def on_message(ws, message):
        message = json.loads(message)
        message = message["imdata"][0]["aaaModLR"]
        print "Websocket Message: {descr}".format(descr=message["attributes"]["descr"])

        spark_message = dedent("""
        New APIC Event!

        {descr}

        DN: {affected}
        Change Set: {changeSet}
        """.format(**message["attributes"])).lstrip('\n').rstrip('\n')

        room.send_message(ss, spark_message)
        print "  - Update sent to Spark room {room}".format(room=room)

    def on_error(ws, error):
        print error

    def on_close(ws):
        print "### closed ###"

    def on_open(ws):
        r = s.get(
            "https://{apic_address}/api/node/class/aaaModLR.json?subscription=yes&order-by=aaaModLR.created|desc&page=0&page-size=15".format(
                apic_address=apic_address), verify=False)
        if not r.ok:
            exit("Failed to subscribe to aaaModLR")

    print ""
    print "==================================================="
    print "Sparci"
    print "==================================================="
    print ""

    print "Authenticating with Spark"
    ss = Session('https://api.ciscospark.com', spark_key)

    try:
        room = Room.get(ss, spark_room)
    except ValueError:
        exit("  Exiting as I failed to authenticate your Spark API key")

    if type(room) == list:
        print "  So, I couldn't find the room {spark_room}, but I did find:".format(spark_room=spark_room)
        for r in room:
            print "   -", r
        print "  maybe try one of those?"
        exit()
    else:
        print "  Found Spark room {room}".format(room=room)
        print ""

    print "Authenticating with APIC"
    data = {
        "aaaUser": {
            "attributes": {
                "name": apic_user,
                "pwd": apic_pass
            }
        }
    }

    s = requests.Session()
    s.headers.update({'Content-Type': 'application/json'})
    r = s.post('https://{apic_address}/api/aaaLogin.json'.format(apic_address=apic_address), json=data, verify=False)

    if not r.ok:
        exit(" Failed to authenticate with APIC")

    auth = r.json()["imdata"][0]["aaaLogin"]
    token = auth["attributes"]["token"]
    print "  Session token = {token}...".format(token=str.join('', token[0:15]))
    print ""
    print "==================================================="
    print "Subscribing to system audit logs"
    print "==================================================="
    print ""

    if debug:
        websocket.enableTrace(True)
    ws = websocket.WebSocketApp("ws://{apic_address}/socket{token}".format(apic_address=apic_address, token=token),
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    ws.on_open = on_open
    ws.run_forever()


if __name__ == "__main__":
    sparci(auto_envvar_prefix="SPARCI")
