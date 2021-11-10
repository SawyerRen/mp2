#!/usr/local/bin/python3.10
"""
    @caution -> use "{}" to quote a str for json decode. It's "{}" not '{}'! very important
"""
import sys
import time
import timeout_decorator
from enum import Enum
import random

TIMEOUT_BASE = 2
HEARTBEAT = 1
TIMEOUT_INF = 1000

if len(sys.argv) != 3:
    raise IndexError("wrong command line format\n")

try:
    pid, total = int(sys.argv[1]), int(sys.argv[2])
except:
    raise TypeError("please input Integer\n")


class StateType(Enum):
    FOLLOWER = 0
    LEADER = 1
    CANDIDATE = 2


class StateMachine(object):
    electionAlarm = random.random() * 4 + TIMEOUT_BASE  # make sure timeout > heartbeat

    def __init__(self):
        self.term = 1
        self.state = StateType.FOLLOWER
        self.commitIndex = 0
        self.voteFor = None
        self.quorum = 0
        self.peers = {}
        for i in range(total):  # store other processes' states
            if i == pid:
                continue
            self.peers[str(i)] = {
                'pid': int(i),
                'nextIndex': 1,
                'matchIndex': 0,
                'voteGranted': False,
                'timeout': 0
            }


@timeout_decorator.timeout(StateMachine.electionAlarm)
def waitingMessage():
    line = sys.stdin.readline()
    return line


def main():
    stateMachine = StateMachine()

    while True:
        try:
            line = waitingMessage()
            line = line.strip().split(' ')
            if line[0] != "RECEIVE":
                print(f"wrong format", flush=True)
                break
            messageSender, messageType, messageTerm, elements = line[1], line[2], int(line[3]), line[4:]

            if messageType == "RequestVotes":
                # TODO: we need new election method according to log condition, not every CANDIDATE -> LEADER

                # if message term is higher
                #   -> FOLLOWER
                #   -> update term
                #   -> vote for sender
                #   -> quorum = 0
                #   -> send RequestVotesResponse
                #   -> reset timeout
                if messageTerm > stateMachine.term:
                    stateMachine.term = messageTerm
                    stateMachine.voteFor = messageSender
                    stateMachine.quorum = 0
                    stateMachine.state = StateType.FOLLOWER
                    print(f"SEND {messageSender} RequestVotesResponse {stateMachine.term} true", flush=True)
                # elif message term == current term
                elif messageTerm == stateMachine.term and stateMachine.state != StateType.LEADER:
                    # if stateMachine.state is CANDIDATE, reject the request
                    if stateMachine.state == StateType.CANDIDATE:
                        print(f"SEND {messageSender} RequestVotesResponse {stateMachine.term} false", flush=True)
                    # else
                    #   -> FOLLOWER
                    #   -> vote for sender
                    #   -> quorum = 0
                    #   -> send RequestVotesResponse
                    #   -> reset timeout
                    else:
                        stateMachine.voteFor = messageSender
                        stateMachine.quorum = 0
                        stateMachine.state = StateType.FOLLOWER
                        print(f"SEND {messageSender} RequestVotesResponse {stateMachine.term} true", flush=True)
                # else message term < current term
                else:
                    pass
                StateMachine.electionAlarm = random.random() * 4 + TIMEOUT_BASE

            elif messageType == "RequestVotesResponse":
                isAgree = elements[0]
                # if message term is higher
                #   -> FOLLOWER
                #   -> update term
                #   -> vote for sender
                #   -> quorum = 0
                # NOTICE: I don't know who is leader, don't reset timeout
                if messageTerm > stateMachine.term:
                    stateMachine.quorum = 0
                    stateMachine.term = messageTerm
                    stateMachine.state = StateType.FOLLOWER
                    continue  # I don't know who is leader, don't reset timeout
                elif messageTerm == stateMachine.term and stateMachine.state == StateType.CANDIDATE:
                    # if reply "true"
                    #   -> quorum += 1
                    #   -> update peers
                    if isAgree == "true":
                        stateMachine.quorum += 1
                        stateMachine.peers[str(messageSender)]['voteGranted'] = True
                        # if quorum exceeds half, can be selected as leader
                        #   -> state -> LEADER  -> send STATE
                        #   -> send AppendEntries
                        if stateMachine.quorum > total // 2 + 1:
                            stateMachine.state = StateType.LEADER
                            print(f'STATE state="{stateMachine.state.name}"', flush=True)
                            print(f'STATE leader="{pid}"', flush=True)
                            for p in stateMachine.peers.keys():
                                # TODO: no sure whether the last parameter is leader id
                                # TODO: add log info
                                print(f"SEND {p} AppendEntries {stateMachine.term} {pid}", flush=True)
                            # TODO: how to set real INF timeout
                            StateMachine.electionAlarm = TIMEOUT_INF  # leader doesn't need timeout
                            continue
                    else:
                        stateMachine.peers[str(messageSender)]['voteGranted'] = False
                else:
                    pass
                StateMachine.electionAlarm = random.random() * 4 + TIMEOUT_BASE

            elif messageType == "AppendEntries":
                # if message term is higher
                #   -> FOLLOWER
                #   -> update term
                #   -> vote for sender
                #   -> quorum = 0
                # NOTICE: I know the leader is the sender
                if messageTerm > stateMachine.term:
                    stateMachine.quorum = 0
                    stateMachine.term = messageTerm
                    stateMachine.voteFor = messageSender
                    stateMachine.term = messageTerm
                elif messageTerm == stateMachine.term:
                    print(f"STATE term={stateMachine.term}", flush=True)
                    stateMachine.voteFor = messageSender
                    print(f'STATE leader="{messageSender}"', flush=True)
                    stateMachine.state = StateType.FOLLOWER
                    print(f'STATE state="{stateMachine.state.name}"', flush=True)

                    # TODO: when add log, we need to change status (true) according to log condition
                    print(f"SEND {messageSender} AppendEntriesResponse {stateMachine.term} true", flush=True)
                else:
                    pass
                StateMachine.electionAlarm = random.random() * 4 + TIMEOUT_BASE

            # receive appendEntriesResponse -> is leader -> send appendEntries periodically
            elif messageType == "AppendEntriesResponse":
                time.sleep(HEARTBEAT)
                for p in stateMachine.peers.keys():
                    # TODO: no sure whether the last parameter is leader id
                    # TODO: add log info
                    print(f"SEND {p} AppendEntries {stateMachine.term} {pid}", flush=True)

            else:
                print(f"wrong message type", flush=True)
                break

        except timeout_decorator.TimeoutError:
            stateMachine.term += 1  # new term
            stateMachine.state = StateType.CANDIDATE  # become CANDIDATE
            stateMachine.voteFor = pid  # vote for myself
            stateMachine.quorum = 1  # quorum ++
            stateMachine.voteFor = None

            # send STATE information and send RequestVote to peers
            print(f"STATE term={stateMachine.term}", flush=True)
            print(f'STATE state="{stateMachine.state.name}"', flush=True)
            for p in stateMachine.peers.keys():
                print(f"SEND {p} RequestVotes {stateMachine.term}", flush=True)
        except KeyboardInterrupt:
            print(f"{pid} stopped")
            break


if __name__ == "__main__":
    main()
