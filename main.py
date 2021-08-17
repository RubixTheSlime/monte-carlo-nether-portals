#!/usr/bin/python3

import pygame as pg
import numpy as np
import math
import sys
import random
from copy import deepcopy
from enum import Enum, auto

class settings:
    # Framerate in frames per second
    framerate = 10

    # Number of generations to advance each frame
    iterations_per_frame = 10

    # Probability (out of one) to split a line (create a new portal) instead of moving it.
    split_chance = 0.1

    # Probability of accepting a 'bad change', out of the number of portal tiles it would lose.
    # Eg 5.0 means that it has a 5/6 chance of accepting the breakage of a 2x3 portal.
    regress_chance = 3.0

    # Size of the bounding obsidian. The inside area will stretch this far out from the center
    radius = 44

    # Whether or not to show the debug info
    debug = True

    # Whether to start with the simulation paused
    start_paused = False

    # Resolution of the window
    res = (640,640)

    # Rectangle that the portals are displayed in
    box = pg.Rect(10,10,620,620)

    # Colors
    obsidian = (0,0,0)
    bg = (255,255,255)
    portal = (255,128,255)




class Block(Enum):
    obsidian = auto()
    portal = auto()
    air = auto()

class Board:
    def __init__(self, radius=None, copy_from = None):
        if copy_from is None:
            self.table = [[Block.air for i in range(math.ceil(radius)*2+1)] for j in range(math.ceil(radius)*2+1)]
            self.spawn_spots = 0
            self.radius = radius
        else:
            self.table = copy_from.table[:]
            self.radius = copy_from.radius
            self.spawn_spots = copy_from.spawn_spots
        self.radiusi = math.ceil(radius)
        self.total_iterations = 0

    def draw(self, surface, bounds):
        px_width = bounds.width / (len(self.table)+2)
        px_height = bounds.width / (len(self.table)+2)

        # draw the obbby outline
        pg.draw.rect(surface, settings.obsidian, bounds)
        pg.draw.rect(surface, settings.bg, (bounds.left+px_width, bounds.top+px_height, bounds.width-px_width*2, bounds.height-px_height*2))

        # draw the blocks
        for row, y in zip(self.table, np.arange(bounds.left+px_width, bounds.right-px_width, px_width)):
            for cell, x in zip(row, np.arange(bounds.top+px_width, bounds.bottom-px_width, px_height)):
                if cell == Block.obsidian:
                    pg.draw.rect(surface, settings.obsidian, (x, y, px_width+1, px_height+1))
                elif cell == Block.portal:
                    pg.draw.rect(surface, settings.portal, (x, y, px_width+1, px_height+1))

    def __getitem__(self, key):
        ''' this is only really defined for (numpy) vectors. (0,0) is the middle, with normal euclidean directions for x and y
        if out of bounds, will always be true
        '''

        row = self.radiusi - key[1]
        col = self.radiusi + key[0]
        if row < 0 or col < 0:
            return Block.obsidian
        try:
            return self.table[row][col]
        except IndexError:
            return Block.obsidian

    def __setitem__(self, key, value):
        ''' this is only really defined for (numpy) vectors. (0,0) is the middle, with normal euclidean directions for x and y
        '''
        row = self.radiusi - key[1]
        col = self.radiusi + key[0]
        if row < 0 or col < 0:
            return
        try:
            self.table[row][col] = value
        except IndexError:
            # fail silently
            pass

    def propogate_line_move(self, cell, prop, move, split):
        ''' moves lines i guess
        cell is the vector for the cell to move
        prop is the propogation direction
        move is the direction to move the cell
        split is whether to split or just move

        returns the first block that can't be moved
        '''
        # terminate if we've hit a T
        # alternatively, terminate at a corner if spliting
        if self[cell + move] == Block.obsidian and (split or self[cell - move] == Block.obsidian):
            return cell
        # ... or if we're not even on an obsidian
        if self[cell] != Block.obsidian:
            return  cell

        # break any portals
        if not split:
            self.break_portal(cell - move)
        self.break_portal(cell + move)

        # move the obby
        self[cell + move] = Block.obsidian

        if not split :
            # leave the block if:
            #   splitting, and
            #   there's an obsidian behind it, but not if both diagonals adjacent to that are obsidian
            self[cell] = Block.obsidian if (
                    self[cell-move]==Block.obsidian
                    and (self[cell - move + prop] != Block.obsidian
                    or self[cell - move - prop] != Block.obsidian
                    )) else Block.air

        # propogate forward
        return self.propogate_line_move(cell + prop, prop, move, split)

    def move_line(self, cell, direction, split):
        '''moves the line the cell belongs to in the direction
        if split is true, the line will be copied instead of moved
        split is overridden in some situations'''

        # direction of propogation, perpendicular to the move direction
        prop = np.array([[0,-1],[1,0]]) @ direction

        # if moving an out of bounds line, always split
        if (       cell[0] < -self.radiusi
                or cell[1] < -self.radiusi
                or cell[0] >  self.radiusi
                or cell[1] >  self.radiusi ):
            if not split:
                return #anyways
            # however, if it would spread into a 3x3, don't do it at all
            if (self[cell + direction*2]==Block.obsidian):
                return
            split = True
        # if it would create a 3x3 block of obsidian, it is always moved
        if (
                (self[cell - direction]==Block.obsidian
                    and self[cell - direction + prop]==Block.obsidian
                    and self[cell - direction - prop]==Block.obsidian)
                or (self[cell + direction*2]==Block.obsidian
                    and self[cell + direction*2 + prop]==Block.obsidian
                    and self[cell + direction*2 - prop]==Block.obsidian)
                ):
            split = False


        # start the two propogations
        # these won't necessarily be the top and bottom, only if propogating upwards
        # but it's easier to think of it that way
        top = self.propogate_line_move(cell, prop, direction, split)
        bottom = self.propogate_line_move(cell - prop, -prop, direction, split)

        # attempt to relight any portals
        block = deepcopy(bottom)
        while not all(block == top):
            self.light_portal(block)
            self.light_portal(block + 2 * direction)
            block += prop


    def light_portal(self, cell):
        '''attempt to light a portal at the specified block.
        assumes there are no "islands" inside the frame
        also assumes that there are no gaps in the frame
        '''
        # terminate quickly if not air
        if self[cell] != Block.air:
            return

        # find the boundaries of the frame
        midx = left = right = self.radiusi + cell[0]
        midy = top = bottom = self.radiusi - cell[1]
        end = len(self.table) - 1
        while left >= 0 and self.table[midy][left] == Block.air:
            left -= 1
        while bottom <= end and self.table[bottom][midx] == Block.air:
            bottom += 1
        while right <= end and self.table[midy][right] == Block.air:
            right += 1
        while top >= 0 and self.table[top][midx] == Block.air:
            top -= 1

        # check the size
        # dimensions are one lower because we're subtracting, which doesn't include the final block
        if not (3 <= right - left <= 22):
            return
        if not (4 <= bottom - top <= 22):
            return

        # at this point we are assuming that the portal is valid
        for col in range(left+1, right):
            for row in range(top+1, bottom):
                self.table[row][col] = Block.portal
        self.spawn_spots += (right - left - 1) * (bottom - top - 1)



    def break_portal(self, cell):
        '''attempt to break a portal at the specified block, java style (for now)'''
        def recurse(row, col):
            if not (0 <= row < len(self.table) and 0 <= col < len(self.table)):
                return
            if self.table[row][col] == Block.portal:
                self.table[row][col] = Block.air
                self.spawn_spots -= 1
                recurse(row,col-1)
                recurse(row,col+1)
                recurse(row-1,col)
                recurse(row+1,col)
        if self[cell] == Block.portal:
            recurse(self.radiusi - cell[1], self.radiusi + cell[0])

    def iteration(self):
        '''perform one monte carlo iteration'''
        # find an obsidian block. may be one block out of bounds
        self.total_iterations += 1
        cell = None
        while True:
            cell = np.array([random.randint(-len(self.table) // 2 , len(self.table) // 2 + 1) for i in range(2)])
            if self[cell]==Block.obsidian:
                break
        direction = np.array(random.choice([[0,1],[1,0],[0,-1],[-1,0]]))

        copy = deepcopy(self)
        copy.move_line(cell, direction, random.random() < settings.split_chance)
        # The monte carlo "sometimes get worse anyways"
        if copy.spawn_spots >= self.spawn_spots or random.random() < settings.regress_chance / (self.spawn_spots-copy.spawn_spots):
            self.table = copy.table
            self.spawn_spots = copy.spawn_spots

def main():
    pg.init()
    screen = pg.display.set_mode(settings.res)
    clk = pg.time.Clock()
    board = Board(radius=settings.radius)
    running = not settings.start_paused
    font = pg.font.SysFont(None, 30)
    ticks = 0
    while True:
        # events
        for event in pg.event.get():
            # Quit when pressing close
            if event.type == pg.QUIT:
                pg.quit()
                sys.exit()
            if event.type == pg.KEYDOWN:
                # Toggle running when pressing p
                if event.key == pg.K_p:
                    running ^= True
                if event.key == pg.K_SPACE and not running:
                    # step once
                    board.iteration()
        ticks +=1
        if running:
            for i in range(settings.iterations_per_frame):
                board.iteration()
        # draw
        screen.fill(settings.bg)
        board.draw(screen, settings.box)

        if settings.debug:
            img = font.render(bytes(f'{clk.get_fps():.3} fps, generation {board.total_iterations}', 'utf-8'), True, (127,127,127))
            screen.blit(img,(0,0))
        pg.display.update()
        clk.tick(settings.framerate)


if __name__ == '__main__':
    main()
