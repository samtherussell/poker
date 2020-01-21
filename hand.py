
from player import Player
from hand_scorer import get_hand_max

class HandPlayer(Player):
 
    def __init__(self, player, hand):
        super().__init__(player.ID, player.name, player.coms, player.holdings)
        self.bet_amount = 0
        self.folded = False
        self.hand = hand
 
    def bet(self, amount):
        super().bet(amount)
        self.bet_amount += amount
 
    def fold(self):
        self.folded = True

class Pot:

    def __init__(self, amount=0, bet=0, players=[]):
        self.amount = amount
        self.bet = bet
        self.playing_players = players

    def __repr__(self):
        return "Pot({}, {}, {})".format(self.amount, self.bet, self.playing_players)

class Bet:

    def __init__(self, amount, who):
        self.amount = amount
        self.who = who

    def __repr__(self):
        return "<{}~{}>".format(self.who, self.amount)
class Bets(dict):

    def total_raise(self):
        sum = 0
        for ID in self:
            sum += self[ID].amount
        return sum

    def max_raise(self):
        return max((self[ID].amount for ID in self)) if len(self) > 0 else 0


def deal_hands(deck, num_players):
 
    hands = [[] for _ in range(num_players)]
 
    for i in range(2):
        for p in range(num_players):
            hands[p].append(deck.pop())
   
    return hands
 
def deal_comm_cards(deck, discard):
 
    comm_cards = []
    deal_order = [discard, comm_cards, comm_cards, comm_cards, discard, comm_cards, discard, comm_cards]
    for pile in deal_order:
        pile.append(deck.pop())
       
    return comm_cards

def get_players_options(current_player, current_bet, has_bet):
    options = ["Fold", "Call"]
    diff = current_bet - current_player.bet_amount
    if current_player.ID not in has_bet and current_player.holdings > diff:
        options.append("Raise")
    return options

def get_raise_amount(action):
    action = action.split(" ")
    if len(action) != 2:
        raise Exception("there is no amount to raise by")
    return int(action[1])

class OnePlayerLeftException(Exception):
    def __init__(self, player):
        self.player = player

class Hand():
 
    def __init__(self, players, deck, start_pos):
 
        self.deck = deck
        self.all_players = players
         
        self.discard = []
        self.hands = deal_hands(self.deck, len(players))
        self.all_hand_players = [HandPlayer(p, h) for p,h in zip(players, self.hands)]
        self.face_down_community_cards = deal_comm_cards(self.deck, self.discard)
        self.face_up_community_cards = []
 
        self.start_pos = start_pos
        self.pot = Pot(0, 0, list(self.all_hand_players))
        self.pots = [self.pot]

        print("Hand initiated:", str(self))

    def put_cards_back_in_deck(self):
        self.deck.extend(self.discard)
        self.deck.extend([card for hand in self.hands for card in hand])
        self.deck.extend(self.face_up_community_cards)
        self.deck.extend(self.face_down_community_cards)

    def run(self):

        self.notify_players("----New Hand----")
        self.notify_player_statuses()
        self.deal_hands()

        try:
            self.run_bet_round(blinds=True)
            self.reveal_cards(3)
            self.run_bet_round()
            self.reveal_cards(1)
            self.run_bet_round()
            self.reveal_cards(1)
            self.run_bet_round()
            self.decide_winner()
        except OnePlayerLeftException as e:
            self.make_winner(e.player)

        self.put_cards_back_in_deck()
        self.update_player_holdings()

    def update_player_holdings(self):
        for player,hand_player in zip(self.all_players, self.all_hand_players):
            player.holdings = hand_player.holdings
            print(player.holdings)

    def make_winner(self, winner):
        print("winner:", winner)
        winner.win(self.pot.amount)
        winner.coms.send_line("YOU WIN\nWinnings: {}".format(self.pot.amount - winner.bet_amount))
        self.notify_players("YOU LOSE", exclude=winner.ID)

    def make_draw(self, winners):
        print("winner:s", winners)
        for winner in winners:
            winner.win(self.pot.amount/2)
            winner.coms.send_line("YOU DRAW\nWinnings: {}".format(self.pot.amount/2 - winner.bet_amount))
        self.notify_players("YOU LOSE", exclude=[w.ID for w in winners])

    def notify_players(self, s, exclude=None):
        for player in self.pot.playing_players:
            if exclude is None \
              or type(exclude) == int and player.ID is not exclude \
              or type(exclude) == list and player.ID not in exclude:
                player.coms.send_line(s)

    def notify_player_statuses(self):
        for player in self.pot.playing_players:
            player.coms.send_line("Money left: {}".format(player.holdings))

    def assign_blinds(self, small_blind=5, big_blind=10):
        if self.start_pos > len(self.pot.playing_players):
            raise Exception("start position larger than number of players")

        if small_blind > big_blind:
            raise Exception("Small blind is bigger than big blind")

        small_blind_enable = len(self.pot.playing_players) > 2

        self.notify_players("big blind is {}".format(big_blind))
        self.notify_players("small blind is {}".format(small_blind) if small_blind_enable else "no small blind")

        bets = []
        for i,player in enumerate(self.pot.playing_players):
            if i == (self.start_pos-1) % len(self.pot.playing_players):
                player.bet(big_blind)
                player.coms.send_line("You are big blind")
                bets.append(Bet(big_blind, player))
            elif small_blind_enable and i == (self.start_pos-2) % len(self.pot.playing_players):
                player.bet(small_blind)
                player.coms.send_line("You are small blind")
                bets.append(Bet(small_blind, player))
            else:
                player.coms.send_line("You are not the blind")

        return bets

    def deal_hands(self):
        for player in self.pot.playing_players:
            player.coms.send_hand(player.hand)
        print("dealt hands")

    def run_bet_round(self, blinds=False):

        def prevp(index):
            return (index - 1) % len(self.pot.playing_players)

        def nextp(index):
            return (index + 1) % len(self.pot.playing_players)

        has_bet = set()
        bets = Bets()

        if blinds:
            blind_bets = self.assign_blinds()
            for bet in blind_bets:
                bets[bet.who.ID] = bet

        current_index = self.start_pos
        round_end_index = prevp(current_index)
        while True:
            current_player = self.pot.playing_players[current_index]
            if not current_player.folded and current_player.has_money():
                available_options = get_players_options(current_player, self.pot.bet, has_bet)
                has_bet.add(current_player.ID)
                print("bets", bets)
                current_pot = self.pot.amount + bets.total_raise()
                current_pot_bet = self.pot.bet + bets.max_raise()
                current_player_bet = current_player.bet_amount
                current_player_holdings = current_player.holdings
                status = "current pot: {}\ncurrent pot bet: {}\nyour current bet: {}\nyour holdings: {}" \
                    .format(current_pot, current_pot_bet, current_player_bet, current_player_holdings)
                print(status)
                current_player.coms.send_line(status)

                while True:
                    current_player.coms.send_line("/".join(available_options))
                    action = current_player.coms.recv(20)
                    print("action:'{}'".format(action))

                    try:
                        if action == "Fold":
                            current_player.fold()
                            display = "Folded"
                            break
                        elif action == "Call":
                            display = self.call_bet(current_player, bets)
                            break
                        elif "Raise" in available_options and action.startswith("Raise"):
                            display = self.raise_bet(current_player, action, bets)
                            round_end_index = prevp(current_index)
                            break
                        else:
                            raise Exception("Invalid command")
                    except Exception as e:
                        current_player.coms.send_line(str(e))

                self.notify_players("{} {}".format(current_player.name, display), exclude=current_player.ID)

            left_in = [p for p in self.pot.playing_players if not p.folded]
            if current_index == round_end_index or len(left_in) < 2:
                break
            current_index = nextp(current_index)

        max_raise = bets.max_raise()
        if all([bets[ID].amount == max_raise for ID in bets]):
            self.pot.bet += max_raise
            self.pot.amount += bets.total_raise()
        else:
            bets = list(bets.values())
            bets.sort(key=lambda x: x.amount)
            current_pot = self.pots.pop()
            base_pot_amount = current_pot.amount
            prev_pot_bet = current_pot.bet
            while len(bets) > 0:
                bet = bets[0]
                new_bet = bet.amount + prev_pot_bet
                new_pot = base_pot_amount + bet.amount * len(bets)
                self.pots.append(Pot(new_pot, new_bet, [bet.who for bet in bets]))
                for bet in bets:
                    bet.amount -= bet.amount
                bets = [bet for bet in bets if bet.amount <= 0]
                prev_pot_bet = new_bet
                base_pot_amount = 0
            self.pot = self.pots[-1]

        self.pot.playing_players = [p for p in self.pot.playing_players if not p.folded]
        if len(self.pot.playing_players) < 2:
            raise OnePlayerLeftException(self.pot.playing_players[0])
        self.start_pos = self.start_pos % len(self.pot.playing_players)


    def call_bet(self, current_player, bets):
        current_max_bet = self.pot.bet + bets.max_raise()
        diff = min(current_max_bet - current_player.bet_amount, current_player.holdings)
        current_player.bet(diff)
        if current_player.ID in bets:
            bets[current_player.ID].amount += diff
        else:
            bets[current_player.ID] = Bet(diff, current_player)
        return "Called"

    def raise_bet(self, current_player, action, bets):
        raise_amount = get_raise_amount(action)
        current_max_bet = self.pot.bet + bets.max_raise()
        diff = (current_max_bet - current_player.bet_amount) + raise_amount
        if current_player.holdings < diff:
            raise Exception("not enough money to raise by " + str(raise_amount))
        current_player.bet(diff)
        if current_player.ID in bets:
            bets[current_player.ID].amount += diff
        else:
            bets[current_player.ID] = Bet(diff, current_player)
        print("Pot raised by {} to {}".format(raise_amount, current_player.bet_amount))
        return "Raised by {} to {}".format(raise_amount, current_player.bet_amount)

    def reveal_cards(self, num):
        cards = self.face_down_community_cards[:num]
        for player in self.pot.playing_players:
            player.coms.send_card_reveal(cards)

        self.face_down_community_cards = self.face_down_community_cards[num:]
        self.face_up_community_cards = self.face_up_community_cards + cards
        print("revealed cards:", cards)

    def decide_winner(self):

        scores = [(player, get_hand_max(player.hand + self.face_up_community_cards)) for player in self.pot.playing_players]
        scores.sort(key=lambda x: x[1][1], reverse=True)

        print("scores:", scores)

        for score in scores:
            player = score[0]
            trick_name = score[1][0]
            self.notify_players("{} got {}".format(player.name, trick_name), exclude=player.ID)

        for score in scores:
            player = score[0]
            trick_name = score[1][0]
            player.coms.send_line("You got {}".format(trick_name))

        if scores[0][1][1] == scores[1][1][1]:
            winners = [scores[0][0], scores[1][0]]
            self.make_draw(winners)
        else:
            winner = scores[0][0]
            self.make_winner(winner)

    def __repr__(self):
        return "players={}, hands={}, face_up_community_card={}, face_down_community_cards={}, pot={}"\
               .format(self.pot.playing_players, self.hands, self.face_up_community_cards, self.face_down_community_cards, self.pot.amount)
