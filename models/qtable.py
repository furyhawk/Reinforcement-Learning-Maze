import logging
import random
from datetime import datetime

import numpy as np

from environment import Status
from models import AbstractModel


class QTableModel(AbstractModel):
    """ Tabular Q-learning prediction model.

        For every state (here: the agents current location ) the value for each of the actions is stored in a table.
        The key for this table is (state + action). Initially all values are 0. When playing training games
        after every move the value in the table is updated based on the reward gained after making the move. Training
        ends after a fixed number of games, or earlier if a stopping criterion is reached (here: a 100% win rate).
    """
    default_check_convergence_every = 5  # by default check for convergence every # episodes

    def __init__(self, game, **kwargs) -> None:
        """ Create a new prediction model for 'game'.

        :param class Maze game: Maze game object
        :param kwargs: model dependent init parameters
        """
        super().__init__(game, name="QTableModel", **kwargs)
        self.Q = dict()  # table with value for (state, action) combination

    def train(self, stop_at_convergence=False, **kwargs):
        """ Train the model.

            :param stop_at_convergence: stop training as soon as convergence is reached

            Hyperparameters:
            :keyword float discount: (gamma) preference for future rewards (0 = not at all, 1 = only)
            :keyword float exploration_rate: (epsilon) 0 = preference for exploring (0 = not at all, 1 = only)
            :keyword float exploration_decay: exploration rate reduction after each random step (<= 1, 1 = no at all)
            :keyword float learning_rate: (alpha) preference for using new knowledge (0 = not at all, 1 = only)
            :keyword int episodes: number of training games to play
            :return int, datetime: number of training episodes, total time spent
        """
        discount = kwargs.get("discount", 0.90)
        exploration_rate = kwargs.get("exploration_rate", 0.10)
        # % reduction per step = 100 - exploration decay
        exploration_decay = kwargs.get("exploration_decay", 0.995)
        learning_rate = kwargs.get("learning_rate", 0.10)
        episodes = max(kwargs.get("episodes", 1000), 1)
        check_convergence_every = kwargs.get(
            "check_convergence_every",
            self.default_check_convergence_every)

        # variables for reporting purposes
        cumulative_reward = 0
        cumulative_reward_history = []
        win_history = []

        start_list = list()
        start_time = datetime.now()

        # training starts here
        for episode in range(1, episodes + 1):
            # optimization: make sure to start from all possible cells
            if not start_list:
                start_list = self.environment.empty.copy()
            start_cell = random.choice(start_list)
            start_list.remove(start_cell)

            state = self.environment.reset(start_cell)
            # change np.ndarray to tuple so it can be used as dictionary key
            state = tuple(state.flatten())

            while True:
                # choose action epsilon greedy (off-policy, instead of only
                # using the learned policy)
                if np.random.random() < exploration_rate:
                    action = random.choice(self.environment.actions)
                else:
                    action = self.predict(state)
                # step and get next state
                next_state, reward, status = self.environment.step(action)
                next_state = tuple(next_state.flatten())

                cumulative_reward += reward

                if (state, action) not in self.Q.keys(
                ):  # ensure value exists for (state, action) to avoid a KeyError
                    self.Q[(state, action)] = 0.0

                # Q formula with TD
                max_next_Q = max([self.Q.get((next_state, a), 0.0)
                                 for a in self.environment.actions])
                self.Q[(state, action)] += learning_rate * (reward +
                                                            discount * max_next_Q - self.Q[(state, action)])

                if status in (
                        Status.WIN, Status.LOSE):  # terminal state reached, stop training episode
                    break

                state = next_state

                self.environment.render_q(self)

            cumulative_reward_history.append(cumulative_reward)

            logging.info("episode: {:d}/{:d} | status: {:4s} | e: {:.5f}"
                         .format(episode, episodes, status.name, exploration_rate))

            if episode % check_convergence_every == 0:
                # check if the current model does win from all starting cells
                # only possible if there is a finite number of starting states
                w_all, win_rate = self.environment.check_win_all(self)
                win_history.append((episode, win_rate))
                if w_all is True and stop_at_convergence is True:
                    logging.info("won from all start cells, stop learning")
                    break

            exploration_rate *= exploration_decay  # explore less as training progresses

        logging.info(
            "episodes: {:d} | time spent: {}".format(
                episode,
                datetime.now() -
                start_time))

        return cumulative_reward_history, win_history, episode, datetime.now() - \
            start_time

    def q(self, state) -> np.ndarray:
        """ Get q values for all actions for a certain state. """
        if isinstance(state, np.ndarray):
            state = tuple(state.flatten())

        return np.array([self.Q.get((state, action), 0.0)
                        for action in self.environment.actions])

    def predict(self, state):
        """ Policy: choose the action with the highest value from the Q-table.
            Random choice if multiple actions have the same (max) value.

            :param np.ndarray state: game state
            :return int: selected action
        """
        q = self.q(state)

        logging.debug("q[] = {}".format(q))

        # get index of the action(s) with the max value
        actions = np.nonzero(q == np.max(q))[0]
        return random.choice(actions)
