import logging
import random

import matplotlib.pyplot as plt
import numpy as np
from keras.layers import Dense
from keras.layers.advanced_activations import PReLU
from keras.models import Sequential, model_from_json

CELL_EMPTY = 0  # indicates empty cell where the agent can move to
CELL_OCCUPIED = 1  # indicates cell contains a wall and cannot be entered
CELL_CURRENT = 2  # indicates current cell of the agent

# all moves the agent can make, plus a dictionary for textual representation
MOVE_LEFT = 0
MOVE_RIGHT = 1
MOVE_UP = 2
MOVE_DOWN = 3

actions = {
    MOVE_LEFT: "move left",
    MOVE_RIGHT: "move right",
    MOVE_UP: "move up",
    MOVE_DOWN: "move down"
}


class Maze:
    """ A maze with walls. An agent is placed at the start cell and needs to move through the maze to reach the exit cell.

    An agent begins its journey at start_cell. The agent can execute moves (up/down/left/right) in the maze in order
    to reach the exit_cell. Every move results in a reward/penalty which are accumulated during the game. Every move
    gives a small penalty, returning to a cell the agent visited before a bigger penalty and running into a wall a
    large penalty. The reward is only collected when reaching the exit. The game always has a terminal state; in
    the end you win or lose. You lose if you have collected a large number of penalties (then the agent is
    assumed to wander around cluelessly.

    Cell coordinates:
    The cells in the maze are stored as (col, row) or (x, y) tuples. (0, 0) is the upper left corner of the maze. This
    way of storing coordinates is in line with what the plot() function expects.
    The maze itself is stored as a 2D array so cells are accessed via [row, col]. To convert a (col, row) tuple to
    (row, col) use: (col, row)[::-1] -> (row, col)
    """

    def __init__(self, maze, start_cell=(0, 0), exit_cell=None):
        """ Create a new maze with a specific start- and exit cell.

        :param numpy.array maze: 2D Array containing empty cells and cells occupied with walls.
        :param tuple start_cell: Starting cell for the agent in the maze (optional, else upper left).
        :param tuple exit_cell: Exit cell which the agent has to reach (optional, else lower right).
        """
        self.maze = maze
        self.display = False  # draw moves or not
        self.minimum_reward = -0.25 * self.maze.size

        nrows, ncols = self.maze.shape
        exit_cell = (ncols - 1, nrows - 1) if exit_cell is None else exit_cell

        self.exit_cell = exit_cell
        self.previous_cell = self.current_cell = start_cell
        self.cells = [(c, r) for c in range(ncols) for r in range(nrows)]
        self.empty = [(c, r) for c in range(ncols) for r in range(nrows) if maze[r, c] == CELL_EMPTY]

        if exit_cell not in self.cells:
            raise Exception("Error: exit cell at {} is not inside maze".format(exit_cell))
        if self.maze[exit_cell[::-1]] == CELL_OCCUPIED:
            raise Exception("Error: exit cell at {} is not free".format(exit_cell))

        self.empty.remove(exit_cell)
        self.reset(start_cell)

    def reset(self, start_cell):
        """ Reset the maze to its initial state and place the agent at start_cell.

        :param tuple start_cell: Cell where the agent will start its journey through the maze.
        """
        if start_cell not in self.cells:
            raise Exception("Error: start cell at {} is not inside maze".format(start_cell))
        if self.maze[start_cell[::-1]] == CELL_OCCUPIED:
            raise Exception("Error: start cell at {} is not free".format(start_cell))
        if start_cell == self.exit_cell:
            raise Exception("Error: start- and exit cell cannot be the same {}".format(start_cell))

        self.previous_cell = self.current_cell = start_cell
        self.total_reward = 0.0
        self.visited = set()

        # if display has been enabled then draw the initial maze
        if self.display:
            nrows, ncols = self.maze.shape
            plt.clf()
            plt.xticks(np.arange(0.5, nrows, step=1), [])
            plt.yticks(np.arange(0.5, ncols, step=1), [])
            plt.grid(True)
            plt.plot(*self.current_cell, "rs", markersize=25)  # start is a big red square
            plt.plot(*self.exit_cell, "gs", markersize=25)  # exit is a big green square
            plt.imshow(self.maze, cmap="binary")
            plt.pause(0.05)

    def show(self):
        """ Enable display of the maze and all moves. """
        self.display = True

    def hide(self):
        """ Hide the maze. """
        self.display = False

    def draw(self):
        """ Draw a line from the agents previous to its current cell. """
        plt.plot(*zip(*[self.previous_cell, self.current_cell]), "bo-")  # previous cells are blue dots
        plt.plot(*self.current_cell, "ro")  # current cell is a red dot
        plt.pause(0.05)

    def move(self, action):
        """ Move the agent according to action and return the new state, reward and game status.

        :param int action: The direction of the agents move.
        :return: state, reward, status
        """
        reward = self.update_state(action)
        self.total_reward += reward
        status = self.status()
        state = self.observe()
        return state, reward, status

    def update_state(self, action):
        """ Execute action and collect the reward/penalty.

        :param int action: The direction in which the agent will move.
        :return float: Reward/penalty after the action has been executed.
        """
        possible_actions = self.possible_actions(self.current_cell)

        if not possible_actions:
            reward = self.minimum_reward - 1  # cannot move any more, force end of game
        elif action in possible_actions:
            col, row = self.current_cell
            if action == MOVE_LEFT:
                col -= 1
            elif action == MOVE_UP:
                row -= 1
            if action == MOVE_RIGHT:
                col += 1
            elif action == MOVE_DOWN:
                row += 1

            self.previous_cell = self.current_cell
            self.current_cell = (col, row)

            if self.current_cell == self.exit_cell:
                reward = 1.0  # maximum reward for reaching the exit cell
            elif self.current_cell in self.visited:
                reward = -0.25  # penalty for returning to a cell which was visited earlier
            else:
                reward = -0.04  # penalty for a move which did not result in finding the exit cell

            self.visited.add(self.current_cell)
        else:
            reward = -0.75  # penalty for trying to enter a occupied cell (= a wall)

        return reward

    def possible_actions(self, cell=None):
        """ Create a list with possible actions.

        :param tuple cell: Location of the agent (optional, else current cell).
        :return list: All possible actions.
        """
        if cell is None:
            col, row = self.current_cell
        else:
            col, row = cell

        possible_actions = [MOVE_LEFT, MOVE_RIGHT, MOVE_UP, MOVE_DOWN]  # initially allow all

        # now restrict the initial list
        nrows, ncols = self.maze.shape
        if row == 0 or (row > 0 and self.maze[row - 1, col] == CELL_OCCUPIED):
            possible_actions.remove(MOVE_UP)
        if row == nrows - 1 or (row < nrows - 1 and self.maze[row + 1, col] == CELL_OCCUPIED):
            possible_actions.remove(MOVE_DOWN)

        if col == 0 or (col > 0 and self.maze[row, col - 1] == CELL_OCCUPIED):
            possible_actions.remove(MOVE_LEFT)
        if col == ncols - 1 or (col < ncols - 1 and self.maze[row, col + 1] == CELL_OCCUPIED):
            possible_actions.remove(MOVE_RIGHT)

        return possible_actions

    def status(self):
        """ Determine the game status.

        :return str: Current game status (win/lose/playing).
        """
        if self.current_cell == self.exit_cell:
            return "win"
        if self.total_reward < self.minimum_reward:  # force end after to much loss
            return "lose"

        return "playing"

    def observe(self):
        """ Create a 1*Z copy of the maze (Z = total cell count in the maze), including the agents current location.

        :return numpy.array [1][size]: Maze content as an array of 1*total_cells_in_array.
        """
        state = np.copy(self.maze)
        col, row = self.current_cell
        state[row, col] = CELL_CURRENT  # indicate the agents current location
        return state.reshape((1, -1))


class Experience:
    def __init__(self, model, max_memory=100, discount=0.95):
        self.model = model
        self.discount = discount
        self.memory = list()  # list with 'max_memory' episodes
        self.max_memory = max_memory
        self.num_actions = model.output_shape[-1]

    def remember(self, episode):
        """ Add episode (=[state, move, reward, next_state, status]) to the end of the memory list.
        """
        self.memory.append(episode)
        if len(self.memory) > self.max_memory:
            del self.memory[0]

    def predict(self, state):
        return self.model.predict(state)[0]

    def get_samples(self, sample_size=10):
        state_size = self.memory[0][0].size  # number of cells in maze
        mem_size = len(self.memory)  # how many episodes are currently stored
        sample_size = min(mem_size, sample_size)  # cannot take more samples then available in memory

        states = np.zeros((sample_size, state_size))
        targets = np.zeros((sample_size, self.num_actions))

        for i, j in enumerate(np.random.choice(range(mem_size), sample_size, replace=False)):
            state, move, reward, next_state, status = self.memory[j]
            states[i] = state
            targets[i] = self.predict(state)

            if status == "win":
                targets[i, move] = reward
            else:
                targets[i, move] = reward + self.discount * np.max(self.predict(next_state))

        return states, targets


class DeepQNetwork:
    def __init__(self, game, modelname="model", load=False):
        self.game = game

        if load is False:
            self.model = Sequential()
            # layer 1: equal number of output- and input neurons (= the number of cells in maze)
            self.model.add(Dense(game.maze.size, input_shape=(game.maze.size,)))
            self.model.add(PReLU())
            # layer 2: as many output neurons as there are cells in maze (inputs equal layer 1)
            self.model.add(Dense(game.maze.size))
            self.model.add(PReLU())
            # layer 3: as many output neurons as there are moves
            self.model.add(Dense(len(actions)))
        else:
            self.load(modelname)

        self.model.compile(optimizer="adam", loss="mse")

    def save(self, filename):
        with open(filename + ".json", "w") as outfile:
            outfile.write(self.model.to_json())
        self.model.save_weights(filename + ".h5", overwrite=True)

    def load(self, filename):
        with open(filename + ".json", "r") as infile:
            self.model = model_from_json(infile.read())
        self.model.load_weights(filename + ".h5")

    def train(self, **kwargs):
        epsilon = 0.1
        epochs = kwargs.get("epochs", 10000)
        max_memory = kwargs.get("max_memory", 1000)
        sample_size = kwargs.get("sample_size", 50)
        load_weights = kwargs.get("load_weights", False)
        modelname = kwargs.get("modelname", "model")

        if load_weights:
            self.model.load_weights(modelname + ".h5")

        experience = Experience(self.model, max_memory=max_memory)

        win_history = list()
        history_size = self.game.maze.size // 2
        win_rate = 0.0

        for epoch in range(1, epochs):
            loss = 0.0
            start_cell = random.choice(self.game.empty)
            self.game.reset(start_cell)

            state = self.game.observe()

            episode = 0
            while True:
                possible_actions = self.game.possible_actions()
                if not possible_actions:
                    status = "blocked"
                    break
                previous_state = state
                if np.random.random() < epsilon:
                    action = random.choice(possible_actions)
                else:
                    action = np.argmax(experience.predict(previous_state))

                state, reward, status = self.game.move(action)

                if status in ("win", "lose"):
                    if status == "win":
                        win_history.append(1)
                    else:
                        win_history.append(0)
                    break

                experience.remember([previous_state, action, reward, state, status])
                episode += 1

                inputs, targets = experience.get_samples(sample_size=sample_size)

                h = self.model.fit(
                    inputs,
                    targets,
                    epochs=8,
                    batch_size=16,
                    verbose=0,
                )
                loss = self.model.evaluate(inputs, targets, verbose=0)

            if len(win_history) > history_size:
                win_rate = sum(win_history[-history_size:]) / history_size
                if win_rate > 0.9:
                    epsilon = 0.05

            logging.info("epoch: {:5d}/{:5d} | loss: {:.4f} | episodes: {:03d} | win count: {:03d} | win rate: {:.3f}"
                         .format(epoch, epochs, loss, episode, sum(win_history), win_rate))

            # check if training has exhausted all empty cells and if in all cases the agent won
            if win_rate == 1 and self.completion_check():
                logging.info("reached 100% win rate at epoch: {}".format(epoch))
                break

        self.save(modelname)  # Save trained models weights and architecture

    def play(self, start_cell=(0, 0)):
        """ Play a single game, choosing the next move based in the highest Q from the Q network.

        :param tuple start_cell: Agents initial cell (optional, else upper left).
        :return str: "win" or "lose"
        """
        self.game.reset(start_cell)

        state = self.game.observe()

        while True:
            q = self.model.predict(state)
            action = int(np.argmax(q[0]))
            logging.debug("q = {} | max = {}".format(q, actions[action]))
            state, reward, status = self.game.move(action)
            if self.game.display:
                logging.info("action: {:5s} | reward: {: .2f} | status: {}".format(actions[action], reward, status))
                self.game.draw()
            if status in ("win", "lose"):
                return status

    def completion_check(self):
        """ Play game for every possible start_location. If won for every start_location return True. """
        for cell in self.game.empty:
            if not self.game.possible_actions(cell):
                return False
            if self.play(cell) == "lose":
                return False
        return True


class QNetwork:
    def __init__(self, game):
        """ Create and use a simple neural network for Q learning.

        The network learns the Q values for each action in each state. In the model the state is represented as a
        vector which maps to Q values.

        :param Maze game: Maze game object.
        """
        self.game = game

        self.model = Sequential()
        self.model.add(Dense(game.maze.size, input_shape=(game.maze.size,)))
        self.model.add(PReLU())
        self.model.add(Dense(game.maze.size))
        self.model.add(PReLU())
        self.model.add(Dense(len(actions)))
        self.model.compile(optimizer="adam", loss="mse")

    def train(self):
        """ Tune the Q network by playing a number of games (called episodes).

        Dependent on epsilon, take a random action or base the action on the current Q network. Update the
        Q network after every action.
        """
        # hyperparameters
        epsilon = 0.1  # exploration vs exploitation (0 = only exploit, 1 = only explore)
        discount = 0.9  # importance of future rewards (0 = not at all, 1 = only)
        episodes = 500  # number of training games to play

        wins = 0

        for episode in range(1, episodes):
            start_cell = random.choice(self.game.empty)
            self.game.reset(start_cell)

            state = self.game.observe()

            while True:
                possible_actions = self.game.possible_actions()
                if not possible_actions:
                    status = "blocked"
                    break
                if np.random.random() < epsilon:
                    action = random.choice(possible_actions)
                else:
                    action = np.argmax(self.model.predict(state))

                next_state, reward, status = self.game.move(action)

                if status in ("win", "lose"):
                    target = reward  # no discount needed if a terminal state was reached.
                else:
                    target = reward + discount * np.max(self.model.predict(next_state))

                target_vector = self.model.predict(state)
                target_vector[0][action] = target  # update Q value for this action

                h = self.model.fit(state, target_vector, epochs=1, verbose=0)

                if status in ("win", "lose"):
                    if status == "win":
                        wins += 1
                    break

                state = next_state

            logging.info("episode: {:4d} | status: {:4s} | total wins: {:4d} ({:.2f})"
                         .format(episode, status, wins, wins / episode))

    def play(self, start_cell=(0, 0)):
        """ Play a single game, choosing the next move based in the highest Q from the Q network.

        :param tuple start_cell: Agents initial cell (optional, else upper left).
        :return str: "win" or "lose"
        """
        self.game.show()
        self.game.reset(start_cell)

        state = self.game.observe()

        while True:
            q = self.model.predict(state)
            action = int(np.argmax(q[0]))
            logging.debug("q = {} | max = {}".format(q, actions[action]))
            state, reward, status = self.game.move(action)
            if self.game.display:
                logging.debug("action: {:5s} | reward: {: .2f} | status: {}".format(actions[action], reward, status))
                self.game.draw()
            if status in ("win", "lose"):
                return status


class QTable:
    """ Reinforcement learning via Q-table.

        For every state (= maze layout with the agents current location ) the Q for each of the actions is stored.
        By playing games enough games (= training), and for every move updating the Q's according to the Bellman
        equation, good quality Q's are determined. If the Q's are good enough can be tested by playing a game.

        Note that this implementation scales badly if the size of the maze increases. """

    def __init__(self, game):
        """ Create a Q-table for all possible states. The q's for each action are initially set to 0.

        State is the maze layout + the location of agent in the maze.
        Todo: try to replace this by just the agents current cell as this is the only thing which changes

        :param Maze game: Maze game object.
        """
        self.game = game
        self.qtable = dict()

        for cell in game.cells:
            state = np.copy(self.game.maze)
            col, row = cell
            state[row, col] = CELL_CURRENT
            state = tuple(
                state.flatten())  # convert [1][Z] array to a tuple of array[Z] so it can be used as dictionary key
            self.qtable[state] = [0, 0, 0, 0]  # 4 possible actions, initially all equally good/bad

    def train(self):
        """ Tune the Q-table by playing a number of games (called episodes).

        Take a random action, of base the action on the current Q table. Update the Q table after each action.
        """
        # hyperparameters
        epsilon = 0.1  # exploration vs exploitation (0 = only exploit, 1 = only explore)
        discount = 0.9  # importance of future rewards (0 = not at all, 1 = only)
        learning_rate = 0.3  # speed of learning (0 = do not learn only exploit, 1 = only use most recent information)
        episodes = 500  # number of training games to play

        wins = 0

        for episode in range(1, episodes):
            start_cell = random.choice(self.game.empty)
            self.game.reset(start_cell)

            state = self.game.observe()
            state = tuple(state.flatten())

            while True:
                possible_actions = self.game.possible_actions()
                if not possible_actions:
                    status = "blocked"
                    break
                if np.random.random() < epsilon:
                    action = random.choice(possible_actions)
                else:
                    action = np.nanargmax(self.qtable[state])  # note: this argmax version ignores nan's

                next_state, reward, status = self.game.move(action)
                next_state = tuple(next_state.flatten())

                self.qtable[state][action] += learning_rate * (
                        reward + discount * max(self.qtable[next_state]) - self.qtable[state][action])

                if status in ("win", "lose"):
                    if status == "win":
                        wins += 1
                    break

                state = next_state

                logging.info("episode: {:4d} | status: {:4s} | total wins: {:4d} ({:.2f})"
                             .format(episode, status, wins, wins / episode))

        # replace any initial zero still left for a nan (not-a-number)
        for key in self.qtable:
            self.qtable[key] = [np.nan if q == 0 else q for q in self.qtable[key]]

    def play(self, start_cell=(0, 0)):
        """ Play a single game, choosing the next move based in the highest Q from the Q-table.

        :param tuple start_cell: Agents initial cell (optional, else upper left).
        :return str: "win" or "lose"
        """
        self.game.show()
        self.game.reset(start_cell)

        state = self.game.observe()
        state = tuple(state.flatten())

        while True:
            q = self.qtable[state]
            action = int(np.nanargmax(q))  # action is the index of the highest Q value
            logging.debug("q = {} | max = {}".format(q, actions[action]))
            state, reward, status = self.game.move(action)
            state = tuple(state.flatten())
            if self.game.display:
                logging.info("action: {:5s} | reward: {: .2f} | status: {}".format(actions[action], reward, status))
                self.game.draw()
            if status in ("win", "lose"):
                return status


class Random:
    """ Choose random moves when playing a game. """

    def __init__(self, game):
        self.game = game

    def play(self, start_cell=(0, 0)):
        """ Play a single game, choosing the next move randomly.

        :param tuple start_cell: Agents initial cell (optional, else upper left).
        :return str: "win" or "lose"
        """
        self.game.show()
        self.game.reset(start_cell)

        while True:
            possible_actions = self.game.possible_actions()
            if not possible_actions:
                break
            action = random.choice(possible_actions)
            state, reward, status = self.game.move(action)
            if self.game.display:
                logging.info("action: {:5s} | reward: {: .2f} | status: {}".format(actions[action], reward, status))
                self.game.draw()
            if status in ("win", "lose"):
                return status


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)-8s: %(asctime)s: %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S")

    maze = np.array([
        [0, 1, 0, 0, 0, 0, 0, 0],
        [0, 1, 0, 0, 0, 1, 0, 0],
        [0, 0, 0, 0, 1, 0, 1, 0],
        [0, 0, 0, 1, 0, 0, 0, 0],
        [0, 0, 1, 0, 0, 0, 0, 0],
        [0, 0, 0, 1, 0, 1, 1, 1],
        [0, 1, 0, 1, 0, 0, 0, 0],
        [0, 0, 0, 0, 1, 0, 0, 0]
    ])  # 0 = free, 1 = occupied

    if 0:
        game = Maze(maze)
        model = Random(game)
        model.play(start_cell=(0, 0))

    if 1:
        game = Maze(maze)
        model = DeepQNetwork(game)
        model.train(epochs=100, max_memory=8 * maze.size, sample_size=32)
        game.show()
        model.play(start_cell=(0, 0))
        model.play(start_cell=(0, 4))
        model.play(start_cell=(3, 7))

    if 0:
        game = Maze(maze)
        model = DeepQNetwork(game, modelname="maze", load=True)
        game.show()
        model.play(start_cell=(0, 0))
        model.play(start_cell=(0, 4))
        model.play(start_cell=(3, 7))

    if 0:
        game = Maze(maze)
        model = QNetwork(game)
        model.train()
        model.play(start_cell=(0, 0))
        model.play(start_cell=(0, 4))
        model.play(start_cell=(3, 7))

    if 0:
        game = Maze(maze)
        model = QTable(game)
        model.train()
        model.play(start_cell=(0, 0))
        model.play(start_cell=(0, 4))
        model.play(start_cell=(3, 7))

    plt.show()  # must be here else the image disappears immediately at the end of the program