import copy
from threading import Thread
import pygame
import grpc
import game_pb2_grpc as pb2_grpc
import game_pb2 as pb2
import uuid
from random import randrange
import sys
import time
import numpy as np

thread_working = False
last_thread_time = 0
running = True
position_dict = {}
frame_rate = 60
update_diff_ms = 67
dt_ms = 1000.0/frame_rate
num_pos_to_gen = (int)(update_diff_ms/dt_ms)

extrapolate = False
interpolate = True

#################################################
pygame.init()
size = 1200, 720
pygame.display.set_caption('Client')
screen = pygame.display.set_mode(size)
clock = pygame.time.Clock()
#################################################

#################################################
# Bullet
# rest - bullet is not moving
# fire - bullet is moving
bulletImage = pygame.image.load('bullet.png')
bullet_X = 0
bullet_Y = 500
bullet_speed = 40
bullet_Xchange = 0
bullet_Ychange = 0
bullet_state = "rest"
bullet_angle = 0
#################################################


class gRPC_Interface():
    def __init__(self):
        #grpc client init
        self.host = 'localhost'
        self.server_port = 50051

        # instantiate a channel
        self.channel = grpc.insecure_channel('{}:{}'.format(self.host, self.server_port))

        # bind the client and the server
        self.stub = pb2_grpc.gameStub(self.channel)

    def get_positions(self, id, x, y):
        position = pb2.Position(id=id, x=x, y=y)
        return self.stub.GetServerResponse(position)
    
def get_positions(now, server, id, x, y):
    global position_dict
    global running
    global last_thread_time
    global thread_working

    #If another thread is working, ignore
    if thread_working:
        return
    thread_working = True
    
    #If another thread more recent already worked, ignore
    if last_thread_time > now:
        return
    last_thread_time = now

    try:
        position_dict_tmp = {}
        result = server.get_positions(id=id, x=x, y=y)
        for position in result:
            position_dict_tmp[position.id] = (position.x, position.y, dt_ms, 1)

        key_to_delete = []
        position_dict_final = copy.copy(position_dict)

        for key, value in position_dict_tmp.items():
            tmp_list = []
            if key not in position_dict_final:
                position_dict_final[key] = tmp_list = [value]
            else:
                tmp_list = position_dict_final[key]
                tmp_list.append(value)

            #only keep server valid pos
            pos_final = []
            for pos in tmp_list:
                if pos[3] == 1:
                    pos_final.append(pos)
            pos_final = pos_final[-2:]
                
            #########################################
            #Interpolation
            #Generate pos in-between server valid ones (when we have at leat 2 server valid pos).
            #Players will see others 2*update_diff_ms behind (rtt)
            if len(pos_final) > 1:
                if interpolate:
                    diff_value_x = (pos_final[1][0] - pos_final[0][0]) / num_pos_to_gen
                    diff_value_y = (pos_final[1][1] - pos_final[0][1]) / num_pos_to_gen
                        
                    value_x = pos_final[0][0]
                    value_y = pos_final[0][1]
                    for i in range(num_pos_to_gen):
                        value_x += diff_value_x
                        value_y += diff_value_y
                        pos_final.insert(1+i, (value_x, value_y, dt_ms, 3))

                #Extrapolation
                if extrapolate:
                    init = 0
                    xp = []
                    fpx = []
                    yp = []
                    fpy = []

                    for pos in pos_final:
                        xp.append(init)
                        fpx.append(pos[0])
                        yp.append(init)
                        fpy.append(pos[1])
                        init += dt_ms
                    
                    fit_x = np.polyfit(np.array(xp), np.array(fpx), 1)
                    line_x = np.poly1d(fit_x)

                    fit_y = np.polyfit(np.array(yp), np.array(fpy), 1)
                    line_y = np.poly1d(fit_y)

                    for i in range(num_pos_to_gen + 1):
                        value_x = line_x(init)
                        value_y = line_y(init)
                        pos_final.append((value_x, value_y, dt_ms, 2))
                        init += dt_ms

            #########################################
            position_dict_final[key] = pos_final

        for key, value in position_dict_final.items():
            if key not in position_dict_tmp:
                key_to_delete.append(key)

        for key in key_to_delete:
            position_dict_final.pop(key)

        position_dict.clear()
        position_dict = position_dict_final

    except grpc.RpcError as rpc_error:
        if "Connection refused" in rpc_error.details():
            pass
        else:
            print(rpc_error)
            running = False
    
    thread_working = False

def bullet(x, y):
    global bullet_state    
    bullet_state = "fire"

    rotated_image = bulletImage
    if bullet_Ychange < 0 and bullet_Xchange > 0:
        rotated_image = pygame.transform.rotate(bulletImage, np.rad2deg(-bullet_angle)-90)
    elif bullet_Ychange < 0 and bullet_Xchange < 0:
        rotated_image = pygame.transform.rotate(bulletImage, np.rad2deg(bullet_angle)+90)
    elif bullet_Ychange > 0 and bullet_Xchange < 0:
        rotated_image = pygame.transform.rotate(bulletImage, np.rad2deg(-bullet_angle)+90)
    elif bullet_Ychange > 0 and bullet_Xchange > 0:
        rotated_image = pygame.transform.rotate(bulletImage, np.rad2deg(bullet_angle)-90)

    screen.blit(rotated_image, rotated_image.get_rect(bottomright = (x, y-2)).center)

def main(shouldRender):
    global position_dict
    global running

    global bullet_X
    global bullet_Y
    global bullet_Xchange
    global bullet_Ychange
    global bullet_state
    global bullet_angle
    
    #grpc server init
    server = gRPC_Interface()

    dt = 0
    last_send = 0
    player_id = str(uuid.uuid4())
    player_pos = pygame.Vector2(randrange(screen.get_width()), randrange(screen.get_height()))

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
        
        if shouldRender: screen.fill("purple")

        ###########################################################
        #Game render

        #Send pos every 100ms
        now = time.time()*1000
        if (now - last_send) >= (100):
            thread = Thread(target=get_positions, args=(now, server, player_id, player_pos.x, player_pos.y))
            thread.start()
            last_send = now

        ###########################################################
        if shouldRender:
            for key, value in position_dict.items():

                if extrapolate: 
                    display_val = ()
                    index_to_play = 1 + num_pos_to_gen + 1
                    if len(value) > index_to_play:
                        display_val = value[index_to_play]
                        del value[index_to_play]
                    else:
                        display_val = value[0]

                    pygame.draw.circle(screen, "blue", pygame.Vector2(display_val[0], display_val[1]), 40)
                elif interpolate:
                    if len(value) > 1:
                        tmp = position_dict[key]
                        del tmp[0]
                        position_dict[key] = tmp
                    pygame.draw.circle(screen, "blue", pygame.Vector2(value[0][0], value[0][1]), 40)
                else:
                    pygame.draw.circle(screen, "blue", pygame.Vector2(value[-1][0], value[-1][1]), 40)
        ###########################################################

        #Draw local player pos last
        if shouldRender: pygame.draw.circle(screen, "red", player_pos, 40)

        keys = pygame.key.get_pressed()
        if keys[pygame.K_z]:
            player_pos.y -= 300 * dt
        if keys[pygame.K_s]:
            player_pos.y += 300 * dt
        if keys[pygame.K_q]:
            player_pos.x -= 300 * dt
        if keys[pygame.K_d]:
            player_pos.x += 300 * dt
        if keys[pygame.K_SPACE]:
            # Fixing the change of direction of bullet
            if bullet_state is "rest":
                Mouse_x, Mouse_y = pygame.mouse.get_pos()
                a = player_pos.y - Mouse_y
                b = Mouse_x - player_pos.x
                bullet_angle = np.arctan(abs(a)/abs(b))
                abis = bullet_speed * np.cos(bullet_angle)
                bbis = bullet_speed * np.sin(bullet_angle)

                if b < 0:
                    abis = abis * -1
                if a < 0:
                    bbis = bbis * -1

                bullet_X = player_pos.x
                bullet_Y = player_pos.y
                bullet_Xchange = abis
                bullet_Ychange = bbis
                bullet(bullet_X, bullet_Y)

        if player_pos.x < 0 : player_pos.x = 0
        if player_pos.x > size[0] : player_pos.x = size[0]
        if player_pos.y < 0 : player_pos.y = 0
        if player_pos.y > size[1] : player_pos.y = size[1]

        # bullet movement

        if bullet_X < 0 : bullet_state = "rest"
        if bullet_X > size[0] : bullet_state = "rest"
        if bullet_Y < 0 : bullet_state = "rest"
        if bullet_Y > size[1] : bullet_state = "rest"

        if bullet_state is "fire":
            bullet(bullet_X, bullet_Y)
            bullet_Y -= bullet_Ychange
            bullet_X += bullet_Xchange
        ###########################################################

        if shouldRender: pygame.display.flip()
        dt = clock.tick(frame_rate) / 1000


if __name__ == "__main__":
    render = True
    if len(sys.argv) == 2:
        render = sys.argv[1] == 'True'

    main(render)