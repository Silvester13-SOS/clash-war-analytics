import sys
import requests
import json
from clash_list_dict import clan_list1

headers = {
        'Accept': 'application/json',
        'authorization': "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiIsImtpZCI6IjI4YTMxOGY3LTAwMDAtYTFlYi03ZmExLTJjNzQzM2M2Y2NhNSJ9.eyJpc3MiOiJzdXBlcmNlbGwiLCJhdWQiOiJzdXBlcmNlbGw6Z2FtZWFwaSIsImp0aSI6ImM2NWMxYzdkLTZlODQtNDYyOC1hYmQ5LWJjMmU5YjcxYmM5ZCIsImlhdCI6MTcyNjQyOTM0Nywic3ViIjoiZGV2ZWxvcGVyL2VhOTMxZWEzLTYxYjAtODA0MS1kZjc3LTAzZDA2ZGM3NDQ2OSIsInNjb3BlcyI6WyJjbGFzaCJdLCJsaW1pdHMiOlt7InRpZXIiOiJkZXZlbG9wZXIvc2lsdmVyIiwidHlwZSI6InRocm90dGxpbmcifSx7ImNpZHJzIjpbIjk4Ljk3LjkuMTMwIl0sInR5cGUiOiJjbGllbnQifV19.NhUDCzpNVzcfg1caOPOkHEtrPoptfJIktEy3V_K2sRRyuD7SoQ1ZqOMDvsBHW-WIVQJIfjG2qIbse8c_lP5VRw"
}

############################## The Dictionary is commented out as the file "clash_list_dict.py" has the active dictionary in it.
############################## I can edit that file with new user to not touch this script.#########################
# clan_list = {
#     'brocaleb': '908P88J0', 
#     '!!Aristocrat!!': '2VY0YVR08', 
#     'YokoEno': '8JPU0228P', 
#     'Little Roodie!': 'PQP8VQ8Q', 
#     'Roodies Raiders': 'YUQ0UQJV', 
#     'Neo': 'VQQ0LGPQ', 
#     'Luke': 'P9QQYCVC', 
#     '■LORD RAJ■': '2V8PVJG', 
#     'Megs Over Easy': '9PP9JL82', 
#     'ItsTwinkie': 'YGJYYCJ2', 
#     'alalalalalala': 'PP9QLQYY', 
#     'kat': '98JQG9R98', 
#     'CRASH': '2UQ2UGY8G', 
#     'rackam': '28PVPV2LU', 
#     'Ryan': '29JPVQ8Q', 
#     'Luffy': '28PQGLVYL', 
#     'jay': 'QCR0UYJ2', 
#     'hay': '99CJPCY9L', 
#     'Juliet': 'GJQCY2U', 
#     'Zookstar123': 'L892JRQ89', 
#     'MonseurMaiDra': '880YP8LQC', 
#     'Chris': 'QC2G880UG', 
#     'Trumpy': 'Q9QQCVLV', 
#     'PlausibleAnt': '9VCU9RJPC', 
#     'The Aristocrat': 'PCLY8GLL', 
#     'KornHub': 'R8VQU9YL', 
#     '69 For Dayz': 'YQ2U0P8Q', 
#     'weel': '8R08JVRP', 
#     'Big Aristocrat': 'RP2YJVPP', 
#     'LoonGoon': 'GPRL28R9', 
#     'patrick': 'LLRYQPP89', 
#     'Inception': 'PCP2G9U8', 
#     'Super Bee': 'UVGQPYVV', 
#     'RONNIE': '90RQY0YCY', 
#     'adanac10': '28GVR820U', 
#     '♡♡DEBADRITA♡♡': '8829LRQP', 
#     'babyrackam': 'LJL89Y8G8', 
#     "PlausibleShan't": 'QPQ9228LQ', 
#     'eeBrepuS': '28GJJYU0J', 
#     'Joe': 'J9VQ28QQ', 
#     'BABY dom': '9GURLYGC', 
#     'Joseph': 'U2R9PR9V', 
#     'biglopp': '8CPVGU0V', 
#     'Legend Hash': '2829UUQGV', 
#     'anubhab': 'VRCGVLPC', 
#     'Max The Monkey': 'G9JR0JGG', 
#     'spencer': '82Y8L009', 
#     'void': '2C2PRLJYQ', 
#     'Ry Ry': '20YUYLLL', 
#     'Dark Valley': '9RCPY8J9R'
# }
################ Asks the user for a player name to lookup equipment from the clan #################
choice_name = input("Who do you want to lookup by name? Type 'all' for every clan member: NOTE: CASE SENSITIVE ") # Return user profile information
def get_user():
    #choice_name = input("Who do you want to lookup by name? NOTE: CASE SENSITIVE ") # Return user profile information
    """Function to use user input and return the equipment that player has upgraded Single player only."""
    if choice_name in clan_list1:
        id = (clan_list1[choice_name])
        formated_url = f"https://api.clashofclans.com/v1/players/%23{id}"
        response = requests.get(formated_url, headers = headers)
        user_json = response.json()
        equip = user_json['heroEquipment']
        if user_json['name']:
            print(user_json['name'])
        for items in equip:
            print(f"{items['name']}, 'current' {items['level']}, 'max' {items['maxLevel']}")

get_user()

def all_user():
    """Function to pull all players in the dictionary file clash_list_dict.py and print output to player_equipment.txt"""
    if choice_name == "all": #########################  Prints all clan member equipment to a file called player_equipment #################              
        for values in clan_list1.values(): ############### Gets the keys from the dict in clash_list_dict.py
            valuesvar = values ################## Sets the valuesvar to be used below in the url (The url requires player tag without #)
            formated_url = f"https://api.clashofclans.com/v1/players/%23{valuesvar}" ### Creates new URL with player tag choosen by user_input.
            response = requests.get(formated_url, headers = headers) ## Sets the paramaters for requests.get
            user_json = response.json() ########### Sets the response as a variable 
            #print(user_json) ############### Un-comment this to see what the response looks like.
            equip = user_json['heroEquipment'] ##############Sets equip variable pulling out the heroEquipment key and all the values within. 
            if user_json['name']: ######################## Pulls the name key out and provides the name and prints it to the file.
                with open('player_equipment.txt', 'a', encoding='utf-8') as f:
                    f.write("\n")
                    print(user_json['name'], file=f)
                    f.write("\n")
            for items in equip: ################## Pulls the equip value out for the name and prints it to the file. 
                with open('player_equipment.txt', 'a', encoding='utf-8') as f:
                    print(f"{items['name']}, 'current' {items['level']}, 'max' {items['maxLevel']}", file=f)

all_user()


