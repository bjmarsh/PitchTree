import os,sys
import gzip, json, glob
import datetime as dt
from Output import Output
from OutputROOT import OutputROOT
from OutputDF import OutputDF, OutputCSV
from GameState import GameState
from DownloadGames import *

class GameJSONParser:
    ignore_actions = ("Passed Ball", "Wild Pitch", "Caught Stealing 2B",
                      "Caught Stealing 3B", "Defensive Switch", 
                      "Game Advisory","Stolen Base 2B", "Stolen Base 3B", "Defensive Sub",
                      "Injury", "Runner Out", "Pickoff Error 1B", "Balk", "Pitch Challenge",
                      "Pickoff 1B", "Ejection", "Defensive Indiff", "Stolen Base Home",
                      "Pickoff Error 2B", "Other Advance", "Pickoff Caught Stealing 2B",
                      "Pickoff 2B", "Caught Stealing Home","Error", "Pickoff Caught Stealing Home",
                      "Pickoff 3B", "Pickoff Caught Stealing 3B", "Pickoff Error 3B")

    base_map = {'1B':'first', '2B':'second', '3B':'third'}
    runner_dict = {}

    def __init__(self, outputter):
        self.game_state = GameState()
        if not isinstance(outputter, Output):
            raise TypeError("Must provide an Output object to the parser!")
        self.output = outputter
        self.unique_events = []                


    def process_runner(self, runner):
        pid = runner["details"]["runner"]["id"]
        start = runner["movement"]["start"]
        end = runner["movement"]["end"]
        if end not in ["1B","2B","3B","4B","score",None]:
            raise Exception("ERROR unknown runner end state: "+end)
        isScore = (end == "score")
        isOut = runner["movement"]["isOut"]
        
        if start not in [None,"4B"] and getattr(self.game_state, self.base_map[start]) == pid:
            setattr(self.game_state, self.base_map[start], -1)
        if end is not None and end not in ["score","4B"]:
            setattr(self.game_state, self.base_map[end], pid)

        if isScore and self.game_state.home_score > -1:
            if self.game_state.half == "top":
                self.game_state.away_score += 1
            if self.game_state.half == "bottom":
                self.game_state.home_score += 1
    
        self.game_state.base_state = 0
        if self.game_state.first != -1:
            self.game_state.base_state |= (1<<0)
        if self.game_state.second != -1:
            self.game_state.base_state |= (1<<1)
        if self.game_state.third != -1:
            self.game_state.base_state |= (1<<2)

        if isOut:
            self.game_state.o += 1
    
        self.runner_dict[runner["details"]["runner"]["fullName"].replace(".","").replace(" ","")] = pid


    def process_pitch(self, pitch):
        class PitchInfo:
            pass
        pinfo = PitchInfo()

        pinfo.pitchidx = pitch["pitchNumber"]
        pinfo.des = pitch["details"]["description"]
        pinfo.type = pitch["details"]["call"]["code"]
        if "type" in pitch["details"]:
            pinfo.pitch_type = pitch["details"]["type"]["code"]
        elif "Automatic Ball" in pinfo.des:
            pinfo.pitch_type = "IN"
        else:
            pinfo.pitch_type = "UN"

        pinfo.x = pitch["pitchData"]["coordinates"].get("x",-9999)
        pinfo.y = pitch["pitchData"]["coordinates"].get("y",-9999)
        pinfo.px = pitch["pitchData"]["coordinates"].get("pX",-9999)
        pinfo.pz = pitch["pitchData"]["coordinates"].get("pZ",-9999)
        pinfo.pfx_x = pitch["pitchData"]["coordinates"].get("pfxX",-9999)
        pinfo.pfx_z = pitch["pitchData"]["coordinates"].get("pfxZ",-9999)
        pinfo.x0 = pitch["pitchData"]["coordinates"].get("x0",-9999)
        pinfo.y0 = pitch["pitchData"]["coordinates"].get("y0",-9999)
        pinfo.z0 = pitch["pitchData"]["coordinates"].get("z0",-9999)
        pinfo.vx0 = pitch["pitchData"]["coordinates"].get("vX0",-9999)
        pinfo.vy0 = pitch["pitchData"]["coordinates"].get("vY0",-9999)
        pinfo.vz0 = pitch["pitchData"]["coordinates"].get("vZ0",-9999)
        pinfo.ax = pitch["pitchData"]["coordinates"].get("aX",-9999)
        pinfo.ay = pitch["pitchData"]["coordinates"].get("aY",-9999)
        pinfo.az = pitch["pitchData"]["coordinates"].get("aZ",-9999)

        pinfo.break_y = pitch["pitchData"]["breaks"].get("breakY",-9999)
        pinfo.break_angle = pitch["pitchData"]["breaks"].get("breakAngle",-9999)
        # for some reason the break angle is abs() valued in the JSON... correct based on sign of ax
        if pinfo.ax > 0 and pinfo.break_angle > -9998:
            pinfo.break_angle *= -1
        pinfo.break_length = pitch["pitchData"]["breaks"].get("breakLength",-9999)
        pinfo.spin_dir = pitch["pitchData"]["breaks"].get("spinDirection",-9999)
        pinfo.spin_rate = pitch["pitchData"]["breaks"].get("spinRate",-9999)

        pinfo.start_speed = pitch["pitchData"].get("startSpeed",-9999)
        pinfo.end_speed = pitch["pitchData"].get("endSpeed",-9999)
        pinfo.sz_top = pitch["pitchData"].get("strikeZoneTop",-9999)
        pinfo.sz_bot = pitch["pitchData"].get("strikeZoneBottom",-9999)
        pinfo.zone = pitch["pitchData"].get("zone",-1)
        pinfo.nasty = int(pitch["pitchData"].get("nastyFactor",-1))
        pinfo.type_confidence = pitch["pitchData"].get("typeConfidence",-9999)

        if "hitData" in pitch:
            pinfo.hit_x = pitch["hitData"]["coordinates"].get("coordX", -9999)
            pinfo.hit_y = pitch["hitData"]["coordinates"].get("coordY", -9999)
            pinfo.hit_launchAngle = pitch["hitData"].get("launchAngle", -9999)
            pinfo.hit_launchSpeed = pitch["hitData"].get("launchSpeed", -9999)
            pinfo.hit_totalDistance = pitch["hitData"].get("totalDistance", -9999)
            pinfo.hit_location = int(pitch["hitData"].get("location", -1))
            pinfo.hit_hardness = pitch["hitData"].get("hardness", "NONE")
            pinfo.hit_trajectory = pitch["hitData"].get("trajectory", "NONE")


        # print "Inning: {0}, Pitcher: {1}, Batter: {2}, Count: {3}-{4}, Outs: {5}, Pitch Type: {6}, Result: {7}".format(
        #     self.game_state.inning"], self.game_state['pitcher'], self.game_state['batter'], self.game_state['b'], 
        #     self.game_state['s'], self.game_state['o'], pinfo.pitch_type"], pinfo.type"])


        self.output.add_entry(self.game_state, pinfo)

        self.game_state.pitch_counts[self.game_state.pitcher] += 1
        self.game_state.cur_pc = self.game_state.pitch_counts[self.game_state.pitcher]

        if pinfo.type in ['B', '*B', 'V', 'P']:
            self.game_state.b += 1
        if pinfo.type not in ['B','*B','V','P','D','X','E'] and (self.game_state.s < 2 or pinfo.des != "Foul"):
            self.game_state.s += 1


        if pinfo.des != "Hit By Pitch": 
            # sometimes the ball count is broken after a hit by pitch... 
            # shouldn't matter anyway as it's the last pitch of AB
            if self.game_state.b != pitch["count"]["balls"]:
                raise Exception("Balls mismatch! (atBatIndex: {0}, pitchNumber: {1}, {2}, {3})".format(self.game_state.abidx, pitch["pitchNumber"], self.game_state.s, pitch["count"]["strikes"]))
            if self.game_state.s != pitch["count"]["strikes"]:
                raise Exception("Strikes mismatch! (atBatIndex: {0}, pitchNumber: {1}, {2}, {3})".format(self.game_state.abidx, pitch["pitchNumber"], self.game_state.s, pitch["count"]["strikes"]))


    def process_atbat(self, atbat):
        gs = self.game_state

        gs.inning = atbat["about"]["inning"]
        # if the half-inning changes, reset the runners and outs
        if gs.half != atbat["about"]["halfInning"]:
            gs.half = atbat["about"]["halfInning"]
            gs.first = -1
            gs.second = -1
            gs.third = -1
            gs.base_state = 0
            gs.o = 0
            self.runner_dict = {}

        gs.away_score_afterInn = \
            self.inning_scores[(gs.half,gs.inning)][0]
        gs.home_score_afterInn = \
            self.inning_scores[(gs.half,gs.inning)][1]

        gs.abidx = atbat["atBatIndex"]
        gs.b = 0
        gs.s = 0
        gs.batter = atbat["matchup"]["batter"]["id"]
        gs.pitcher= atbat["matchup"]["pitcher"]["id"]
        gs.BH = atbat["matchup"]["batSide"]["code"]
        gs.PH = atbat["matchup"]["pitchHand"]["code"]

        gs.home_score_afterAB = atbat["result"]["homeScore"]
        gs.away_score_afterAB = atbat["result"]["awayScore"]

        # get event type, check if it's the first time we've seen it
        if "event" not in atbat["result"]:
            # a couple of randomly empty at-bats?
            if len(atbat["playEvents"]) == 0:
                return
            else:
                raise Exception("Faulty at-bat! gid: {0}, startTime: {1}".format(gs.gid, atbat["about"]["startTime"]))
        gs.event = atbat["result"]["event"]
        if gs.event not in self.unique_events:
            #print "{0:25s}:{1}".format(gs.event, gs.gid)
            self.unique_events.append(gs.event)

        if gs.pitcher not in gs.pitch_counts:
            gs.pitch_counts[gs.pitcher] = 0

        # each at-bat consists of a series of "events". Each event can be a "pitch" or an
        # "action" (e.g. stolen base).
        # "runners" can be concurrent with each event. Store as [event, [runners1,...]]
        events = []
        for event in atbat["playEvents"]:
            events.append([event, []])
        # for the "after at-bat", there can be runners but no official "event"
        events.append([None, []])
        # now insert the runner events at the appropriate spot
        for runner in atbat["runners"]:
            if runner["movement"]["start"] is None and runner["movement"]["end"] is None and runner["movement"]["isOut"] is None:
                continue
            if runner["movement"]["start"] is not None and runner["movement"]["start"] == runner["movement"]["end"]:
                continue
            idx = runner["details"]["playIndex"]
            events[idx][1].append(runner)

        for event,runners in events:
            if event is not None:
                if event["type"] == "no_pitch":
                    # ??????
                    pass
                elif event["type"] == "pitch":
                    self.process_pitch(event)
                    pass
                elif event["type"] == "action":
                    evttype = event["details"]["event"]
                    if evttype == "Pitching Substitution":
                        gs.pitcher = event["player"]["id"]
                        if gs.pitcher not in gs.pitch_counts:
                            gs.pitch_counts[gs.pitcher] = 0
                    elif evttype == "Umpire Substitution":
                        des = event["details"]["description"]
                        if "HP" in des or "home plate" in des.lower():
                            gs.umpire = event["umpire"]["id"]
                    elif evttype == "Pitcher Switch":
                        if "left-handed" in event["details"]["description"]:
                            gs.PH = "L"
                        if "right-handed" in event["details"]["description"]:
                            gs.PH = "R"
                    elif evttype == "Offensive Substitution":
                        if "pinch-runner" in event["details"]["description"].lower():
                            r_name = event["details"]["description"].split("replaces ")[-1].replace(".","").replace(" ","") \
                                        .replace("CCron","CJCron").replace("JHardy","JJHardy").replace("APollock","AJPollock") \
                                        .replace("AEllis","AJEllis").replace("JMartinez","JDMartinez") \
                                        .replace("NickCastellanosXXX","NicholasCastellanos").replace("NoriAoki","NorichikaAoki") \
                                        .replace("JArencibia","JPArencibia").replace("CarlosSanchez","YolmerSanchez") \
                                        .replace("RickieWeeks","RickieWeeksJr").replace("GiovannyUrshela","GioUrshela") \
                                        .replace("IvanDeJesus","IvanDeJesusJr").replace("APierzynski","AJPierzynski") \
                                        .replace("AReed","AJReed").replace("YulieskiGurriel","YuliGurriel") \
                                        .replace("RonaldAcuna","RonaldAcunaJr").replace("JoseFernandez","JoseMiguelFernandez") \
                                        .replace("AlbertAlmora","AlbertAlmoraJr").replace("VladimirGuerrero","VladimirGuerreroJr") \
                                        .replace("LaMonteWade","LaMonteWadeJr") \
                                        .replace("JrJr","Jr")
                            if r_name not in self.runner_dict:
                                print "runner_dict:", self.runner_dict
                                raise Exception("Pinch-runner replacing {0}, who doesn't appear to be on the bases".format(r_name))
                            pid = self.runner_dict[r_name]
                            for b in ["first","second","third"]:
                                if getattr(gs, b) == pid:
                                    setattr(gs, b,  event["player"]["id"])
                            pr_name = event["details"]["description"].split(" replaces")[0].split("-runner ")[-1].replace(".","").replace(" ","")
                            self.runner_dict[pr_name] = event["player"]["id"]

                    elif evttype == "Runner Placed On Base" and "2nd" in event["details"]["description"]:
                        # stupid 2020 rule where runner starts on second in extras
                        gs.second = event["player"]["id"]
                        gs.base_state = 2
                        name = event["details"]["description"].split(" starts inning")[0].replace(" ","").replace(".","")
                        self.runner_dict[name] = gs.second

                    elif evttype in self.ignore_actions:
                        pass
                    else:
                        raise Exception("Unknown action: "+evttype)
                elif event["type"] not in ["pickoff"]:
                    raise Exception("Unknown event type "+event["type"])

            # holy shit the runner data is a mess
            # out of order, duplicate entries, entries for a runner going from 3B to 3B, etc....
            # a bunch of ad-hoc fixes here to make sure we get it right (only 75% sure that it's doing the right thing...)
            runners = sorted(runners, key=lambda x:x["movement"]["isOut"], reverse=True)
            to_do = list(range(len(runners)))
            isout = []

            while len(to_do)>0:
                idx = to_do[0]
                rid = runners[idx]["details"]["runner"]["id"]
                if runners[idx]["movement"]["start"] == "4B":
                    runners[idx]["movement"]["start"] = "3B"
                if runners[idx]["movement"]["isOut"]:
                    runners[idx]["movement"]["end"] = None
                if runners[idx]["details"]["isScoringEvent"] and runners[idx]["movement"]["end"] == "4B":
                    runners[idx]["movement"]["end"] = "score"
                # now very specific custom overrides for buggy data
                if gs.gamePk==447927 and rid==514888 and gs.inning==9 and gs.half=="bottom" and runners[idx]["movement"]["end"] == "2B":
                    runners[idx]["movement"]["end"] = "3B"
                if gs.gamePk==448903 and rid==592450 and gs.inning==6 and gs.half=="top" and runners[idx]["movement"]["start"] == "2B":
                    runners[idx]["movement"]["start"] = "1B"
                if gs.gamePk==531490 and rid==607208 and gs.inning==1 and gs.half=="bottom" and runners[idx]["movement"]["start"] == "2B":
                    runners[idx]["movement"]["start"] = "1B"
                if gs.gamePk==531651 and rid==624577 and gs.inning==1 and gs.half=="bottom" and runners[idx]["movement"]["start"] == "3B":
                    runners[idx]["movement"]["start"] = "1B"
                if gs.gamePk==565928 and rid==502481 and gs.inning==7 and gs.half=="top" and runners[idx]["movement"]["start"] is None:
                    runners[idx]["movement"]["end"] = None
                    runners[idx]["movement"]["isOut"] = True
                if gs.gamePk==565932 and rid==665742 and gs.inning==1 and gs.half=="bottom" and runners[idx]["movement"]["start"] == "1B":
                    runners[idx]["movement"]["start"] = "2B"
                if gs.gamePk==566213 and rid==516782 and gs.inning==1 and gs.half=="bottom" and runners[idx]["movement"]["start"] == "1B":
                    runners[idx]["movement"]["start"] = "2B"
                if gs.gamePk==566702 and rid==596059 and gs.inning==6 and gs.half=="top" and runners[idx]["movement"]["start"] == "1B":
                    runners[idx]["movement"]["start"] = "3B"
                if gs.gamePk==567416 and rid==623912 and gs.inning==4 and gs.half=="bottom" and runners[idx]["movement"]["start"] == "3B":
                    runners[idx]["movement"]["start"] = "2B"
                if gs.gamePk==566630 and rid==657557 and gs.inning==5 and gs.half=="bottom" and runners[idx]["movement"]["isOut"] == True:
                    to_do = to_do[1:]
                    continue
                if gs.gamePk==566155 and rid==595777 and gs.inning==4 and gs.half=="bottom" and runners[idx]["movement"]["start"] == "2B":
                    runners[idx]["movement"]["start"] = "1B"
                if gs.gamePk==567432 and rid==656371 and gs.inning==4 and gs.half=="bottom" and runners[idx]["movement"]["start"] is None:
                    runners[idx]["movement"]["end"] = "1B"
                if gs.gamePk==565003 and rid==596105 and gs.inning==2 and gs.half=="bottom" and runners[idx]["movement"]["start"] == "1B":
                    runners[idx]["movement"]["start"] = "2B"
                if gs.gamePk==599336 and rid==665742 and gs.inning==8 and gs.half=="bottom" and runners[idx]["movement"]["start"] == "2B":
                    runners[idx]["movement"]["start"] = "1B"
                if gs.gamePk==631014 and runners[idx]["movement"]["end"] == "0B":
                    to_do = to_do[1:]
                    continue

                start = runners[idx]["movement"]["start"]
                end = runners[idx]["movement"]["end"]
                if rid in isout or (end in ["1B","2B","3B"] and getattr(gs, self.base_map[end]) == rid):
                    to_do = to_do[1:]
                    continue
                if start is None and end is None and runners[idx]["movement"]["isOut"]:
                    for bshort, blong in self.base_map.items():
                        if getattr(gs, blong) == rid:
                            start = bshort
                            runners[idx]["movement"]["start"] = bshort
                            break
                    

                # I see no resort other than to just hard code it to skip some particularly buggy ones...
                if (gs.gamePk,gs.inning, gs.half, rid, runners[idx]["details"]["event"]) in \
                   [(380974,12,"bottom",407893,"Defensive Indiff"),
                    (413681,2,"bottom",624577,"Runner Out"),
                    (413681,2,"bottom",624577,"Forceout"),
                    (415742,2,"top",461865,"Double Play"),
                    (447076,7,"bottom",572863,"Runner Out"),
                   ]:
                    to_do = to_do[1:]
                    continue

                # if gs.gid == "2019/09/05/anamlb-oakmlb-1":# and gs.inning==7 and gs.half=="bottom":
                #     print gs.half, gs.inning, gs.o, rid, start, end, gs.first, gs.second, gs.third
                #     raw_input()

                # buggy thing where a runner on 2B has an entry for 3B to score, with no entry for 2B to 3B
                if len(to_do)==1 and end=='score' and start is not None and getattr(gs, self.base_map[start]) != rid:
                    for b in ['first', 'second', 'third']:
                        if getattr(gs, b) == rid:                                        
                            setattr(gs, b, -1)
                    setattr(gs, self.base_map[start], rid)

                # make sure start is None (i.e. it's the batter), or the runner is already at start

                clear_path = True
                if (end=='1B' or start is None and end in ['2B','3B']) and gs.first != -1:
                    clear_path = False
                if (end=='2B' or start in [None, '1B'] and end=='3B') and gs.second != -1:
                    clear_path = False
                if end=='3B' and gs.third != -1:
                    clear_path = False

                # print gs.half, gs.inning, gs.o, rid, start, end, gs.first, gs.second, gs.third

                if (start is None or \
                    getattr(gs, self.base_map[start]) == rid) and \
                   (end in [None, 'score'] or gs.o==3 or clear_path):
                    self.process_runner(runners[idx])
                    to_do = to_do[1:]
                    if end is None or end is 'score':
                        isout.append(rid)
                else:
                    if len(to_do)==1:
                        print gs.half, gs.inning, gs.o, rid, start, end, gs.first, gs.second, gs.third
                        raise Exception("Shouldn't get here, we've reached an infinite loop! See above for state")
                    else:
                        to_do = to_do[1:] + to_do[:1]

        if gs.home_score_afterAB != gs.home_score:
            print gs
            raise Exception("Home score mismatch!")
        if gs.away_score_afterAB != gs.away_score:
            print gs
            raise Exception("Away score mismatch!")

        gs.o = atbat["count"]["outs"]


    def parse_game(self, gd):
        g = gd["gameData"]
        print g["game"]["id"], g["game"]["pk"], g["datetime"]["dateTime"]

        self.game_state = GameState()

        # get some auxiliary info about game
        self.game_state.gid = g["game"]["id"]
        self.game_state.gamePk = g["game"]["pk"]
        date = dt.datetime.strptime(g["datetime"]["dateTime"],"%Y-%m-%dT%H:%M:%SZ")
        if date.hour <= 5:
            date -= dt.timedelta(1)
        date = date.date()
        hour = int(g["datetime"]["time"].split(":")[0])
        if g["datetime"]["ampm"] == "PM" and hour != 12:
            hour += 12
        minute = int(g["datetime"]["time"].split(":")[1])
        self.game_state.date = dt.datetime(date.year, date.month, date.day, hour, minute)
        self.game_state.away_team = g["teams"]["away"]["teamCode"]
        self.game_state.home_team = g["teams"]["home"]["teamCode"]
        self.game_state.DH = int(g["game"]["id"].split("-")[-1])

        # get HP umpire
        ld = gd["liveData"]
        umps = ld["boxscore"]["officials"]
        for ump in umps:
            if "home" in ump["officialType"].lower():
                self.game_state.umpire = ump["official"]["id"]

        # get the score after each inning, for use later
        innings = ld["linescore"]["innings"]
        ch, ca = 0, 0
        self.inning_scores = {}
        for inn in innings:
            ca += inn["away"]["runs"]
            self.inning_scores[("top",inn["num"])] = (ca,ch)
            if "home" in inn and "runs" in inn["home"]:
                ch += inn["home"]["runs"]
            self.inning_scores[("bottom",inn["num"])] = (ca,ch)

        # loop over all plays
        for play in ld["plays"]["allPlays"]:
            if play["result"]["type"] == "atBat":
                self.process_atbat(play)
            else:
                raise Exception("Unknown play type "+events["result"]["type"])


if __name__=="__main__":
    
    output = OutputDF("pitches_test.pkl")
    # output = OutputCSV("pitches_test.csv")
    # output = OutputROOT("pitches_test.root")
    parser = GameJSONParser(output)
    # pks = get_gamePks(dt.date(2019,06,11),dt.date(2019,06,12),teamId=112)
    pks = [491288]    
    for pk in pks:
        d = download_single_game(pk)
        if d:
            parser.parse_game(d)
    # ds = download_dates(dt.date(2019,06,11),dt.date(2019,06,12),teamId=112)
    # for d in ds:
    #     parser.parse_game(d)

    output.write()
