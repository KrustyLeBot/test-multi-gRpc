import copy
import pygame
import grpc
import game_pb2_grpc as pb2_grpc
import game_pb2 as pb2
from concurrent import futures
import time
import uuid
from random import randrange

position_dict = {}

class GameService(pb2_grpc.gameServicer):

    def __init__(self, *args, **kwargs):
        pass

    def GetServerResponse(self, request, context):
        id = request.id
        x = request.x
        y = request.y

        #Insert pos into cache
        position_dict[id] = (x, y, time.time())

        position_dict_copy = copy.copy(position_dict)
        for key, value in position_dict_copy.items():
            if key != id:
                result = {'id': key, 'x': value[0], 'y': value[1]}
                yield pb2.Position(**result)


def blit_text(surface, text, pos, font, color=pygame.Color('black')):
    words = [word.split(' ') for word in text.splitlines()]  # 2D array where each row is a list of words.
    space = font.size(' ')[0]  # The width of a space.
    max_width, max_height = surface.get_size()
    x, y = pos
    for line in words:
        for word in line:
            word_surface = font.render(word, 0, color)
            word_width, word_height = word_surface.get_size()
            if x + word_width >= max_width:
                x = pos[0]  # Reset the x.
                y += word_height  # Start on new row.
            surface.blit(word_surface, (x, y))
            x += word_width + space
        x = pos[0]  # Reset the x.
        y += word_height  # Start on new row.


def main():
    #grpc server init
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=64))
    pb2_grpc.add_gameServicer_to_server(GameService(), server)
    server.add_insecure_port('[::]:50051')
    server.start()

    pygame.init()
    size = 800, 400
    pygame.display.set_caption('Server')
    screen = pygame.display.set_mode(size)
    clock = pygame.time.Clock()
    pygame.font.init()
    font = pygame.font.SysFont('Arial', 8)
    running = True

    dt = 0
    render = True
    #render = False

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
        if render: screen.fill("black")

        ###########################################################
        #Server processing
        
        #Clean cache after 1sec
        now = time.time()
        text = f'Positions, {len(position_dict)} clients:\n'
        key_to_delete = []
        for key, value in position_dict.items():
            text += f'id: {key}, x:{value[0]}, y:{value[1]}\n'
            if (now - value[2]) > 1:
                key_to_delete.append(key)

        for key in key_to_delete:
            position_dict.pop(key)

        if render: blit_text(screen, text, (0,0), font, pygame.Color('white'))
        ###########################################################

        if render: pygame.display.flip()
        dt = clock.tick(60) / 1000
    
    server.stop(0)


if __name__ == "__main__":
    main()